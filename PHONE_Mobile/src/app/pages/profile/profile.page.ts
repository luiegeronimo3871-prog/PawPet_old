import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { IonContent, IonButton, IonItem, IonInput, IonSelect, IonSelectOption, AlertController, ToastController } from '@ionic/angular';
import { ApiService, Pet, passwordProblem } from '../../services/api.service';

@Component({
  selector: 'app-profile',
  imports: [FormsModule, IonContent, IonButton, IonItem, IonInput, IonSelect, IonSelectOption],
  template: `
  <ion-content>
    <div class="page">
      <h1 class="hello">Profile</h1>
      <div class="card row">
        <div class="avatar" style="background:var(--pp-green);color:#fff;font-weight:700">{{ initial }}</div>
        <div class="grow"><b>{{ api.user()?.full_name }}</b><div class="sub" style="margin:0">{{ api.user()?.email || api.user()?.username }}</div>
          <div class="sub" style="margin:0">{{ api.user()?.phone }}</div></div>
      </div>

      <h3 class="sec">My pets</h3>
      @if (error) { <div class="err">{{ error }}</div> }
      @for (p of pets; track p.id) {
        <div class="card row">
          <div class="avatar">{{ p.species === 'Cat' ? '🐱' : '🐶' }}</div>
          <div class="grow"><b>{{ p.name }}</b>
            <div class="sub" style="margin:0">{{ p.breed || p.species }}@if (p.age) {, {{ p.age }} yr}@if (p.weight) {, {{ p.weight }} kg}</div>
            @if (p.notes) { <small style="color:#a86a0a">{{ p.notes }}</small> }</div>
          <ion-button size="small" fill="clear" color="danger" (click)="remove(p)">Remove</ion-button>
        </div>
      } @empty { <div class="card empty">No pets yet. Add one below.</div> }

      <h3 class="sec">Add a pet</h3>
      <ion-item class="field"><ion-input label="Pet name" labelPlacement="floating" maxlength="60" [(ngModel)]="form.name"></ion-input></ion-item>
      <ion-item class="field"><ion-select label="Species" labelPlacement="floating" [(ngModel)]="form.species">
        @for (s of speciesList; track s) { <ion-select-option [value]="s">{{ s }}</ion-select-option> }</ion-select></ion-item>
      <ion-item class="field"><ion-input label="Breed" labelPlacement="floating" maxlength="60" [(ngModel)]="form.breed"></ion-input></ion-item>
      <div class="row">
        <ion-item class="field grow"><ion-input label="Age (years)" labelPlacement="floating" type="number" min="0" [(ngModel)]="form.age"></ion-input></ion-item>
        <ion-item class="field grow"><ion-input label="Weight (kg)" labelPlacement="floating" type="number" min="0" [(ngModel)]="form.weight"></ion-input></ion-item>
      </div>
      <ion-item class="field"><ion-input label="Notes (allergies, medication)" labelPlacement="floating" maxlength="255" [(ngModel)]="form.notes"></ion-input></ion-item>
      <ion-button class="pp" expand="block" (click)="add()">Save pet</ion-button>

      <h3 class="sec">Change password</h3>
      @if (pwError) { <div class="err">{{ pwError }}</div> }
      <ion-item class="field"><ion-input label="Current password" labelPlacement="floating" type="password" autocomplete="current-password" maxlength="128" [(ngModel)]="pw.old"></ion-input></ion-item>
      <ion-item class="field"><ion-input label="New password (8+, letters and numbers)" labelPlacement="floating" type="password" autocomplete="new-password" maxlength="128" [(ngModel)]="pw.new1"></ion-input></ion-item>
      <ion-item class="field"><ion-input label="Repeat new password" labelPlacement="floating" type="password" autocomplete="new-password" maxlength="128" [(ngModel)]="pw.new2"></ion-input></ion-item>
      <ion-button class="pp" expand="block" fill="outline" (click)="changePw()">Update password</ion-button>

      <ion-button class="pp" expand="block" fill="outline" color="danger" style="margin-top:28px" (click)="logout()">Log out</ion-button>
    </div>
  </ion-content>`,
})
export class ProfilePage {
  api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);
  private router = inject(Router);
  private alerts = inject(AlertController);
  private toasts = inject(ToastController);
  pets: Pet[] = [];
  error = ''; pwError = '';
  pw = { old: '', new1: '', new2: '' };
  speciesList = ['Dog', 'Cat', 'Bird', 'Rabbit', 'Hamster', 'Other'];
  form: { name: string; species: string; breed: string; age: string | number; weight: string | number; notes: string } =
    { name: '', species: 'Dog', breed: '', age: '', weight: '', notes: '' };

  get initial() { return (this.api.user()?.full_name || '?')[0]; }

  private entered = false;
  ngOnInit() { this.entered = true; return this.load(); }
  ionViewWillEnter() { if (this.entered) { this.entered = false; return; } return this.load(); }
  private async load() {
    try { await this.loadInner(); } finally { this.cdr.detectChanges(); }
  }

  private async loadInner() {
    try { this.pets = await this.api.pets(); } catch (e) { this.error = (e as Error).message; }
  }

  async add() {
    this.error = '';
    if (!this.form.name.trim()) { this.error = 'Enter your pet\'s name.'; return; }
    const age = this.form.age === '' ? null : Number(this.form.age);
    const weight = this.form.weight === '' ? null : Number(this.form.weight);
    if ((age !== null && (isNaN(age) || age < 0)) || (weight !== null && (isNaN(weight) || weight < 0))) { this.error = 'Age and weight must be positive numbers.'; return; }
    try {
      await this.api.addPet({ name: this.form.name.trim(), species: this.form.species, breed: this.form.breed, age, weight, notes: this.form.notes });
      this.form = { name: '', species: 'Dog', breed: '', age: '', weight: '', notes: '' };
      (await this.toasts.create({ message: 'Pet saved 🐾', duration: 1800, color: 'success' })).present();
      await this.load();
    } catch (e) { this.error = (e as Error).message; }
  }

  async remove(p: Pet) {
    const alert = await this.alerts.create({
      header: `Remove ${p.name}?`, buttons: [{ text: 'Keep', role: 'cancel' }, {
        text: 'Remove', role: 'destructive',
        handler: async () => {
          try { await this.api.deletePet(p.id); await this.load(); }
          catch (e) { this.error = (e as Error).message; }
        },
      }],
    });
    await alert.present();
  }

  async changePw() {
    this.pwError = '';
    if (!this.pw.old) { this.pwError = 'Enter your current password.'; this.cdr.detectChanges(); return; }
    if (this.pw.new1 !== this.pw.new2) { this.pwError = 'The two new passwords do not match.'; this.cdr.detectChanges(); return; }
    const problem = passwordProblem(this.pw.new1);
    if (problem) { this.pwError = problem; this.cdr.detectChanges(); return; }
    try {
      await this.api.changePassword(this.pw.old, this.pw.new1);
      this.pw = { old: '', new1: '', new2: '' };
      (await this.toasts.create({ message: 'Password updated', duration: 2000, color: 'success' })).present();
    } catch (e) { this.pwError = (e as Error).message; }
    this.cdr.detectChanges();
  }

  async logout() {
    await this.api.logout();
    this.api.hardReset();          // reload so the next person never sees this person's data
  }
}
