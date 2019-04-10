import {Component} from '@angular/core';
import {MatDialogRef} from '@angular/material';

@Component({
  selector: 'app-confirmation-dialog',
  templateUrl: 'confirmation-dialog.component.html',
})
export class ConfirmationDialogComponent {
  public confirmMessage: string;
  public proceedMessage: string;
  public cancelMessage: string;

  constructor(public dialogRef: MatDialogRef<ConfirmationDialogComponent>) {
    this.proceedMessage = 'Enter';
    this.cancelMessage = 'Cancel';
  }
}