import {Component, ElementRef, OnDestroy, OnInit, ViewChild} from '@angular/core';
import {Router} from '@angular/router';
import {ApiService} from '../api.service';
import {FormControl, FormGroup, Validators} from '@angular/forms';
import {Entry} from '../nmrstar/entry';
import {Subscription} from 'rxjs';

@Component({
  selector: 'app-welcome',
  templateUrl: './welcome.component.html',
  styleUrls: ['./welcome.component.scss']
})
export class WelcomeComponent implements OnInit, OnDestroy {
  entry: Entry;
  @ViewChild('inputFile') fileUploadElement: ElementRef;
  subscription$: Subscription;

  constructor(private router: Router,
              public api: ApiService) {
    this.entry = null;
  }

  sessionType = new FormControl('', [Validators.required]);
  authorEmail = new FormControl('', [
    Validators.required,
    Validators.email,
  ]);
  depositionNickname = new FormControl('', [Validators.required]);
  authorORCID = new FormControl('', [Validators.pattern(/^\d{4}-\d{4}-\d{4}-(\d{3}X|\d{4})$/)]);
  bootstrapID = new FormControl('', [Validators.required, Validators.pattern(/^[0-9]+$/)]);

  createDepositionForm: FormGroup = new FormGroup({
    sessionType: this.sessionType,
    authorEmail: this.authorEmail,
    depositionNickname: this.depositionNickname,
    authorORCID: this.authorORCID,
  });

  getEmailErrorMessage(emailForm: FormControl) {
    return emailForm.hasError('required') ? 'You must enter your email address.' :
      emailForm.hasError('email') ? 'Not a valid email address.' : '';
  }

  getBootstrapErrorMessage(bootstrapForm: FormControl) {
    return bootstrapForm.hasError('required') ? 'You must enter the ID of an existing entry.' :
      bootstrapForm.hasError('pattern') ? 'Not a valid BMRB ID.' : '';
  }

  ngOnInit() {
    this.subscription$ = this.api.entrySubject.subscribe(entry => {
      this.entry = entry;
    });
  }

  ngOnDestroy() {
    this.subscription$.unsubscribe();
  }

  // This is needed for angular to detect the file upload
  fileChangeEvent() {
  }

  openInput() {
    this.fileUploadElement.nativeElement.click();
  }

  new(f: FormGroup) {

    if (!f.valid) {
      return;
    }

    let bootstrapID = null;
    if (f.value.sessionType === 'bmrb_id') {
      if (!this.bootstrapID.value) {
        return;
      }
      if (f.value.sessionType === 'bmrb_id') {
        bootstrapID = this.bootstrapID.value;
      }
    }

    let fileElement = null;
    if (f.value.sessionType === 'file') {
      fileElement = this.fileUploadElement.nativeElement.files[0];
    }

    this.api.clearDeposition();
    this.api.newDeposition(f.value.authorEmail, f.value.depositionNickname, f.value.authorORCID, fileElement, bootstrapID).then(
      deposition_id => {
        this.router.navigate(['/entry', 'load', deposition_id]);
      });
  }
}
