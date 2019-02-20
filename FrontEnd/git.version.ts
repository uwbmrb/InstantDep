import { writeFileSync } from 'fs';
import { dedent } from 'tslint/lib/utils';

const util = require('util');
const exec = util.promisify(require('child_process').exec);

async function createVersionsFile(filename: string) {
    const revision = (await exec('git rev-parse --short HEAD')).stdout.toString().trim();
    const branch = (await exec('git rev-parse --abbrev-ref HEAD')).stdout.toString().trim();

    console.log(`revision: '${revision}', branch: '${branch}'`);

    const content = dedent`
      // this file is automatically generated by git.version.ts script
      export const versions = {
        revision: '${revision}',
        branch: '${branch}'
      };
`;

    writeFileSync(filename, content, {encoding: 'utf8'});
}

createVersionsFile('src/environments/versions.ts');
