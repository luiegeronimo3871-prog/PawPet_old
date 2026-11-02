import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { IonContent, IonButton, IonItem, IonInput, IonSegment, IonSegmentButton, IonLabel, IonSpinner } from '@ionic/angular';
import { ApiService, passwordProblem } from '../../services/api.service';

@Component({
  selector: 'app-login',
  imports: [FormsModule, IonContent, IonButton, IonItem, IonInput, IonSegment, IonSegmentButton, IonLabel, IonSpinner],
  template: `
  <ion-content>
    <div class="top">
      <div class="logo">🐾</div>
      <h1>PawPet</h1>
      <p>Care for your pets, one tap away.</p>
    </div>
    <div class="page">
      @if (mode !== 'change') {
        <ion-segment [value]="mode" (ionChange)="mode = $any($event.detail.value); error = ''">
          <ion-segment-button value="login"><ion-label>Sign in</ion-label></ion-segment-button>
          <ion-segment-button value="register"><ion-label>Create account</ion-label></ion-segment-button>
        </ion-segment>
      }

      @if (mode === 'change') {
        <div style="margin-top:18px">
          <h3 style="margin:0 0 6px">Choose a new password</h3>
          <p class="hint" style="text-align:left;margin:0 0 12px">Your password was set by the clinic. Please pick your own (8+ characters, with letters and numbers).</p>
          <ion-item class="field"><ion-input label="New password" labelPlacement="floating" type="password" autocomplete="new-password" maxlength="128" [(ngModel)]="newPassword"></ion-input></ion-item>
          <ion-item class="field"><ion-input label="Repeat new password" labelPlacement="floating" type="password" autocomplete="new-password" maxlength="128" [(ngModel)]="newPassword2" (keyup.enter)="submit()"></ion-input></ion-item>
          @if (error) { <div class="err">{{ error }}</div> }
          <ion-button class="pp" expand="block" (click)="submit()" [disabled]="busy">
            @if (busy) { <ion-spinner name="dots"></ion-spinner> } @else { Save password }
          </ion-button>
        </div>
      } @else {
      <div style="margin-top:18px">
        @if (mode === 'register') {
          <ion-item class="field"><ion-input label="Full name" labelPlacement="floating" maxlength="100" [(ngModel)]="full_name"></ion-input></ion-item>
          <ion-item class="field"><ion-input label="Phone" labelPlacement="floating" type="tel" maxlength="30" [(ngModel)]="phone"></ion-input></ion-item>
          <ion-item class="field"><ion-input label="Email" labelPlacement="floating" type="email" maxlength="100" [(ngModel)]="email"></ion-input></ion-item>
        }
        <ion-item class="field"><ion-input label="Username" labelPlacement="floating" autocomplete="username" maxlength="50" [(ngModel)]="username"></ion-input></ion-item>
        <ion-item class="field"><ion-input label="Password" labelPlacement="floating" type="password" [attr.autocomplete]="mode === 'login' ? 'current-password' : 'new-password'" maxlength="128" [(ngModel)]="password" (keyup.enter)="submit()"></ion-input></ion-item>
        @if (error) { <div class="err">{{ error }}</div> }
        <ion-button class="pp" expand="block" (click)="submit()" [disabled]="busy">
          @if (busy) { <ion-spinner name="dots"></ion-spinner> } @else { {{ mode === 'login' ? 'Sign in' : 'Create account' }} }
        </ion-button>
        @if (mode === 'login') { <p class="hint">Forgot your password? Ask the clinic to reset it for you.</p> }
        @else { <p class="hint">Password: 8+ characters with letters and numbers.</p> }
      </div>
      }
    </div>
  </ion-content>`,
  styles: [`
    .top { background: linear-gradient(160deg, #0f3b24, #1f5a3a); color: #fff; text-align: center; padding: 56px 20px 40px; border-radius: 0 0 32px 32px; }
    .logo { font-size: 48px; } h1 { margin: 6px 0 4px; font-size: 32px; } p { margin: 0; color: #bfe3cd; }
    .hint { text-align: center; color: var(--pp-muted); font-size: 13px; margin-top: 14px; }
  `],
})
export class LoginPage {
  private api = inject(ApiService);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);
  mode: 'login' | 'register' | 'change' = 'login';
  newPassword = ''; newPassword2 = '';
  username = ''; password = ''; full_name = ''; phone = ''; email = '';
  error = ''; busy = false;

  async submit() {
    this.error = '';
    if (this.mode === 'change') return this.saveNewPassword();
    if (!this.username.trim() || !this.password) { this.error = 'Enter your username and password.'; return; }
    if (this.mode === 'register') {
      if (!this.full_name.trim()) { this.error = 'Enter your full name.'; return; }
      if (!/^[A-Za-z0-9_.\-]{3,50}$/.test(this.username.trim())) { this.error = 'Username: 3-50 letters, numbers, dot, dash or underscore.'; return; }
      if (this.email.trim() && !/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(this.email.trim())) { this.error = 'Enter a valid email address.'; return; }
      if (this.phone.trim() && !/^[0-9+()\- ]{0,30}$/.test(this.phone.trim())) { this.error = 'Phone can only have digits, spaces and + - ( ).'; return; }
      const pwErr = passwordProblem(this.password);
      if (pwErr) { this.error = pwErr; return; }
    }
    this.busy = true;
    this.cdr.detectChanges();
    try {
      if (this.mode === 'register') {
        await this.api.register({ full_name: this.full_name.trim(), username: this.username.trim(), password: this.password, email: this.email.trim(), phone: this.phone.trim() });
      }
      await this.api.login(this.username.trim(), this.password);
      this.oldPassword = this.password;
      this.password = '';
      if (this.api.user()?.must_change) { this.mode = 'change'; return; }
      await this.router.navigateByUrl('/tabs/home', { replaceUrl: true });
    } catch (e) {
      this.error = (e as Error).message || 'Something went wrong. Is the server running?';
      if (this.mode === 'register' && /already taken/i.test(this.error)) this.error += ' Try another one, or switch to Sign in.';
    } finally {
      this.busy = false;
      this.cdr.detectChanges();
    }
  }

  private oldPassword = '';

  private async saveNewPassword() {
    if (this.newPassword !== this.newPassword2) { this.error = 'The two passwords do not match.'; return; }
    const pwErr = passwordProblem(this.newPassword);
    if (pwErr) { this.error = pwErr; return; }
    this.busy = true;
    this.cdr.detectChanges();
    try {
      await this.api.changePassword(this.oldPassword, this.newPassword);
      this.oldPassword = this.newPassword = this.newPassword2 = '';
      await this.router.navigateByUrl('/tabs/home', { replaceUrl: true });
    } catch (e) {
      this.error = (e as Error).message;
    } finally {
      this.busy = false;
      this.cdr.detectChanges();
    }
  }
}
