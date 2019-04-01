#!/usr/bin/env python3

import os
import json

from typing import Optional, BinaryIO, Union, List

# Pip module imports
from git import Repo, CacheError
import werkzeug.utils
import flask
import logging
import pynmrstar
from filelock import Timeout, FileLock

# Local imports
from common import ServerError, RequestError, configuration

if not os.path.exists(configuration['repo_path']):
    try:
        os.mkdir(configuration['repo_path'])
        logging.warning('The deposition root directory did not exist... creating it.')
    except FileExistsError:
        pass


def secure_filename(filename: str) -> str:
    """ Wraps werkzeug secure_filename but raises an error if the filename comes out empty. """

    filename = werkzeug.utils.secure_filename(filename)
    if not filename:
        raise RequestError('Invalid upload file name. Please rename the file and try again.')
    return filename


class DepositionRepo:
    """ A class to interface with git repos for depositions.

    You *MUST* use the 'with' statement when using this class to ensure that
    changes are committed."""

    def __init__(self, uuid, initialize: bool = False):
        self._repo: Repo
        self._uuid = uuid
        self._initialize: bool = initialize
        self._entry_dir: str = os.path.join(configuration['repo_path'], str(self._uuid))
        self._modified_files: bool = False
        self._live_metadata: dict = {}
        self._original_metadata: dict = {}
        self._lock_path: str = os.path.join(configuration['repo_path'], str(uuid), '.git', 'api.lock')
        self._lock_object: Optional[FileLock] = None

        # Make sure the entry ID is valid, or throw an exception
        if not os.path.exists(self._entry_dir):
            if not self._initialize:
                raise RequestError('No deposition with that ID exists!', status_code=404)
            else:
                # Create the entry directory
                os.mkdir(self._entry_dir)
                os.mkdir(os.path.join(self._entry_dir, '.git'))
                os.mkdir(os.path.join(self._entry_dir, 'data_files'))

    def __enter__(self):
        """ Get a session cookie to use for future requests. """

        # Get the lock before doing anything in the directory
        self._lock_object = FileLock(self._lock_path, timeout=10)
        try:
            self._lock_object.acquire()
        except Timeout:
            raise ServerError('Could not get a lock on the deposition directory. This is usually because another'
                              ' request is already in progress.')

        if self._initialize:
            self._repo = Repo.init(self._entry_dir)
            self._repo.config_writer().set_value("user", "name", "BMRBDep").release()
            self._repo.config_writer().set_value("user", "email", "bmrbhelp@bmrb.wisc.edu").release()
        else:
            self._lock_object = FileLock(self._lock_path, timeout=10)
            self._lock_object.acquire()
            self._repo = Repo(self._entry_dir)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ End the current session."""

        # If nothing changed the commit won't do anything
        try:
            self.commit("Repo closed with changed but without a manual commit... Potential software bug.")
            self._repo.close()
            self._repo.__del__()
        # Catches all git-related errors
        except CacheError as err:
            raise ServerError("An exception happened while closing the entry repository: %s" % err)
        finally:
            self._lock_object.release()

    @property
    def metadata(self) -> dict:
        """ Return the metadata dictionary. """

        if not self._live_metadata:
            self._live_metadata = json.loads(self.get_file('submission_info.json'))
            self._original_metadata = self._live_metadata.copy()
        return self._live_metadata

    def get_entry(self) -> pynmrstar.Entry:
        """ Return the NMR-STAR entry for this entry. """

        entry_location = os.path.join(self._entry_dir, 'entry.str')

        try:
            return pynmrstar.Entry.from_file(entry_location)
        except Exception as e:
            raise ServerError('Error loading an entry!\nError: %s\nEntry location:%s' % (repr(e), entry_location))

    def write_entry(self, entry: pynmrstar.Entry) -> None:
        """ Save an entry in the standard place. """

        try:
            self.metadata['last_ip'] = flask.request.environ['REMOTE_ADDR']
        except RuntimeError:
            pass
        self.write_file('entry.str', str(entry).encode(), root=True)

    def get_file(self, filename: str, root: bool = True) -> bytes:
        """ Returns the current version of a file from the repo. """

        secured_filename: str = secure_filename(filename)
        if not root:
            secured_filename = os.path.join('data_files', secured_filename)
        try:
            return open(os.path.join(self._entry_dir, secured_filename), "rb").read()
        except IOError:
            raise RequestError('No file with that name saved for this entry.')

    def get_data_file_list(self) -> List[str]:
        """ Returns the list of data files associated with this deposition. """

        return os.listdir(os.path.join(self._entry_dir, 'data_files'))

    def delete_data_file(self, filename: str) -> None:
        """ Delete a data file by name."""

        secured_filename = secure_filename(filename)
        os.unlink(os.path.join(self._entry_dir, 'data_files', secured_filename))
        self._modified_files = True

    def write_file(self, filename: str, data: bytes, root: bool = False) -> str:
        """ Adds (or overwrites) a file to the repo. Returns the name of the written file. """

        try:
            self.metadata['last_ip'] = flask.request.environ['REMOTE_ADDR']
        except RuntimeError:
            pass

        secured_filename: str = secure_filename(filename)
        file_path: str = secured_filename
        if not root:
            file_path = os.path.join('data_files', secured_filename)

        with open(os.path.join(self._entry_dir, file_path), "wb") as fo:
            fo.write(data)

        self._modified_files = True

        return filename

    def commit(self, message: str) -> bool:
        """ Commits the changes to the repository with a message. """

        # Check if the metadata has changed
        if self._live_metadata != self._original_metadata:
            self.write_file('submission_info.json',
                            json.dumps(self._live_metadata, indent=2, sort_keys=True).encode(),
                            root=True)
            self._original_metadata = self._live_metadata.copy()

        # No recorded changes
        if not self._modified_files:
            return False

        # See if they wrote the same value to an existing file
        if not self._repo.untracked_files and not [item.a_path for item in self._repo.index.diff(None)]:
            return False

        # Add the changes, commit
        self._repo.git.add(all=True)
        self._repo.git.commit(message=message)
        self._modified_files = False
        return True
