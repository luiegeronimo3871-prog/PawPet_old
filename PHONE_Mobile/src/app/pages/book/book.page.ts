import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonButton, IonItem, IonInput, IonSpinner, ToastController } from '@ionic/angular';
import { ApiService, Pet, Service, Vet, Slot, localDate, t12, peso } from '../../services/api.service';

@Component({
  selector: 'app-book',
  imports: [FormsModule, RouterLink, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonButton, IonItem, IonInput, IonSpinner],
  template: `
  <ion-header class="ion-no-border">
    <ion-toolbar><ion-buttons slot="start"><ion-back-button defaultHref="/tabs/home" text=""></ion-back-button></ion-buttons><ion-title>Book Appointment</ion-title></ion-toolbar>
  </ion-header>
  <ion-content>
    <div class="page">
      @if (loading) { <div class="empty"><ion-spinner></ion-spinner></div> }
      @if (error) { <div class="err">{{ error }}</div> }

      @if (!loading && pets.length === 0) {
        <div class="card empty"><span class="big">🐾</span>Add your pet first so we know who is coming.
          <div style="margin-top:12px"><ion-button routerLink="/tabs/profile">Add a pet</ion-button></div></div>
      } @else if (!loading) {
        <h3 class="sec" style="margin-top:4px">1. Your pet</h3>
        @for (p of pets; track p.id) {
          <div class="pick row" [class.sel]="petId === p.id" (click)="petId = p.id">
            <div class="avatar">{{ p.species === 'Cat' ? '🐱' : '🐶' }}</div>
            <div class="grow"><b>{{ p.name }}</b><div class="sub" style="margin:0">{{ p.breed || p.species }}@if (p.age) {, Age: {{ p.age }} yr}</div></div>
          </div>
        }

        <h3 class="sec">2. Service</h3>
        @for (s of services; track s.id) {
          <div class="pick row" [class.sel]="serviceId === s.id" (click)="serviceId = s.id; loadSlots()">
            <div class="emoji">{{ s.emoji }}</div>
            <div class="grow"><b>{{ s.name }}</b><div class="sub" style="margin:0">{{ s.duration }} min</div></div>
            <b>{{ money(s.price) }}</b>
          </div>
        }

        <h3 class="sec">3. Veterinarian</h3>
        @for (v of vets; track v.id) {
          <div class="pick" [class.sel]="vetId === v.id" (click)="vetId = v.id; loadSlots()">
            <b>{{ v.name }}</b><div class="sub" style="margin:0">{{ v.specialty }} · {{ t(v.start_time) }}–{{ t(v.end_time) }}</div>
          </div>
        }

        <h3 class="sec">4. Date</h3>
        <div class="dates">
          @for (d of days; track d.iso) {
            <div class="d" [class.sel]="date === d.iso" (click)="date = d.iso; loadSlots()">{{ d.dow }}<b>{{ d.day }}</b>{{ d.today ? 'Today' : '' }}</div>
          }
        </div>

        <h3 class="sec">5. Time</h3>
        @if (slotsLoading) { <ion-spinner name="dots"></ion-spinner> }
        @else if (!ready) { <div class="sub">Choose a service, veterinarian and date to see available times.</div> }
        @else if (slots.length === 0) { <div class="sub">This veterinarian is not working on that day. Try another date.</div> }
        @else {
          <div class="slot-grid">
            @for (s of slots; track s.time) {
              <div class="slot" [class.sel]="time === s.time" [class.dis]="!s.available" (click)="s.available && (time = s.time)">{{ t(s.time) }}</div>
            }
          </div>
        }

        <ion-item class="field" style="margin-top:18px"><ion-input label="Notes for the vet (optional)" labelPlacement="floating" maxlength="500" [(ngModel)]="notes"></ion-input></ion-item>
        <ion-button class="pp" expand="block" color="success" (click)="submit()" [disabled]="busy">
          @if (busy) { <ion-spinner name="dots"></ion-spinner> } @else { Book Now }
        </ion-button>
        <p class="sub" style="text-align:center">You will get a confirmation and a reminder in Alerts.</p>
      }
    </div>
  </ion-content>`,
})
export class BookPage {
  private api = inject(ApiService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private toasts = inject(ToastController);
  private cdr = inject(ChangeDetectorRef);

  pets: Pet[] = []; services: Service[] = []; vets: Vet[] = []; slots: Slot[] = [];
  petId = 0; serviceId = 0; vetId = 0; date = ''; time = ''; notes = '';
  loading = true; busy = false; slotsLoading = false; error = '';
  days: { iso: string; dow: string; day: number; today: boolean }[] = [];
  t = t12; money = peso;

  get ready() { return !!(this.serviceId && this.vetId && this.date); }

  private entered = false;
  ngOnInit() { this.entered = true; return this.enter(); }
  ionViewWillEnter() { if (this.entered) { this.entered = false; return; } return this.enter(); }

  private async enter() {
    this.error = ''; this.loading = true; this.time = '';
    try {
      const base = new Date();
      this.days = Array.from({ length: 14 }, (_, i) => {
        const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() + i);
        return { iso: localDate(d), dow: d.toLocaleDateString('en-US', { weekday: 'short' }), day: d.getDate(), today: i === 0 };
      });
      this.date = this.date || this.days[0].iso;
      [this.pets, this.services, this.vets] = await Promise.all([this.api.pets(), this.api.services(), this.api.vets()]);
      const pre = Number(this.route.snapshot.queryParamMap.get('service'));
      if (pre && this.services.some(s => s.id === pre)) this.serviceId = pre;
      if (!this.petId || !this.pets.some(p => p.id === this.petId)) this.petId = this.pets[0]?.id || 0;
      if (!this.vetId && this.vets.length) this.vetId = this.vets[0].id;
      if (!this.serviceId && this.services.length) this.serviceId = this.services[0].id;
      await this.loadSlots();
    } catch (e) {
      this.error = (e as Error).message || 'Could not load the booking page.';
      console.error('Book page error:', e);
    } finally {
      this.loading = false;
      this.cdr.detectChanges();
    }
  }

  private slotSeq = 0;
  async loadSlots() {
    this.time = '';
    if (!this.ready) return;
    const seq = ++this.slotSeq;           // only the newest request may update the screen (slow networks)
    this.slotsLoading = true;
    this.cdr.detectChanges();
    try {
      const slots = await this.api.availability(this.vetId, this.serviceId, this.date);
      if (seq !== this.slotSeq) return;
      this.slots = slots; this.error = '';
    } catch (e) {
      if (seq !== this.slotSeq) return;
      this.error = (e as Error).message; this.slots = [];
    }
    this.slotsLoading = false;
    this.cdr.detectChanges();
  }

  async submit() {
    this.error = '';
    if (!this.petId || !this.serviceId || !this.vetId || !this.date) { this.error = 'Please choose a pet, service, veterinarian and date.'; return; }
    if (!this.time) { this.error = 'Please pick a time.'; return; }
    if (this.busy) return;               // ignore a second tap while the first is still being sent
    this.busy = true;
    this.cdr.detectChanges();
    try {
      await this.api.book({ pet_id: this.petId, service_id: this.serviceId, vet_id: this.vetId, appt_date: this.date, appt_time: this.time, notes: this.notes });
      (await this.toasts.create({ message: 'Appointment booked! 🐾', duration: 2200, color: 'success' })).present();
      this.notes = '';
      await this.router.navigateByUrl('/tabs/appointments', { replaceUrl: true });
    } catch (e) {
      this.error = (e as Error).message;
      // the error banner is at the top of a long page, so also show it where the person is looking
      (await this.toasts.create({ message: this.error, duration: 3500, color: 'danger', position: 'top' })).present();
      await this.loadSlots();  // the slot may have just been taken, refresh the list
    } finally { this.busy = false; this.cdr.detectChanges(); }
  }
}
