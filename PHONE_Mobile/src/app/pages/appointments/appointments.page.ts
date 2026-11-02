import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { IonContent, IonSegment, IonSegmentButton, IonLabel, IonRefresher, IonRefresherContent, IonButton, AlertController, ToastController } from '@ionic/angular';
import { ApiService, Appointment, localDate, t12, prettyDate, peso } from '../../services/api.service';

@Component({
  selector: 'app-appointments',
  imports: [RouterLink, IonContent, IonSegment, IonSegmentButton, IonLabel, IonRefresher, IonRefresherContent, IonButton],
  template: `
  <ion-content>
    <ion-refresher slot="fixed" (ionRefresh)="refresh($event)"><ion-refresher-content></ion-refresher-content></ion-refresher>
    <div class="page">
      <h1 class="hello">My visits</h1>
      <p class="sub">Upcoming appointments and history.</p>
      <ion-segment [value]="tab" (ionChange)="tab = $any($event.detail.value)">
        <ion-segment-button value="upcoming"><ion-label>Upcoming ({{ upcoming.length }})</ion-label></ion-segment-button>
        <ion-segment-button value="history"><ion-label>History</ion-label></ion-segment-button>
      </ion-segment>
      @if (error) { <div class="err">{{ error }}</div> }
      <div style="margin-top:14px">
        @for (a of list; track a.id) {
          <div class="card">
            <div class="row">
              <div class="emoji">{{ a.service_emoji }}</div>
              <div class="grow"><b>{{ a.pet_name }} · {{ a.service_name }}</b>
                <div class="sub" style="margin:2px 0 0">{{ date(a.appt_date) }} at {{ time(a.appt_time) }}<br>{{ a.vet_name }} · {{ money(a.service_price) }}</div></div>
              <span class="badge" [class]="a.status">{{ a.status.replace('_', ' ') }}</span>
            </div>
            @if (a.status === 'pending' || a.status === 'confirmed') {
              <ion-button size="small" fill="outline" color="danger" style="margin-top:10px" (click)="cancel(a)">Cancel</ion-button>
            }
          </div>
        } @empty {
          <div class="empty"><span class="big">📅</span>
            {{ tab === 'upcoming' ? 'No upcoming visits.' : 'No past visits yet.' }}
            @if (tab === 'upcoming') { <div style="margin-top:12px"><ion-button routerLink="/book">Book an appointment</ion-button></div> }
          </div>
        }
      </div>
    </div>
  </ion-content>`,
})
export class AppointmentsPage {
  private api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);
  private alerts = inject(AlertController);
  private toasts = inject(ToastController);
  tab: 'upcoming' | 'history' = 'upcoming';
  all: Appointment[] = [];
  error = '';
  date = prettyDate; time = t12; money = peso;

  private isUpcoming(a: Appointment) { return ['pending', 'confirmed'].includes(a.status) && a.appt_date >= localDate(new Date()); }
  get upcoming() { return this.all.filter(a => this.isUpcoming(a)).sort((a, b) => (a.appt_date + a.appt_time).localeCompare(b.appt_date + b.appt_time)); }
  get history() { return this.all.filter(a => !this.isUpcoming(a)).sort((a, b) => (b.appt_date + b.appt_time).localeCompare(a.appt_date + a.appt_time)); }
  get list() { return this.tab === 'upcoming' ? this.upcoming : this.history; }

  private entered = false;
  ngOnInit() { this.entered = true; return this.load(); }
  ionViewWillEnter() { if (this.entered) { this.entered = false; return; } return this.load(); }
  async refresh(ev: CustomEvent) { await this.load(); ev.detail.complete(); }

  private async load() {
    try { await this.loadInner(); } finally { this.cdr.detectChanges(); }
  }

  private async loadInner() {
    this.error = '';
    try { this.all = await this.api.appointments(); } catch (e) { this.error = (e as Error).message; }
  }

  async cancel(a: Appointment) {
    const alert = await this.alerts.create({
      header: 'Cancel appointment?', message: `${a.pet_name} · ${a.service_name} on ${prettyDate(a.appt_date)}`,
      buttons: [{ text: 'Keep it', role: 'cancel' }, {
        text: 'Cancel visit', role: 'destructive',
        handler: async () => {
          try { await this.api.cancel(a.id); await this.load(); (await this.toasts.create({ message: 'Appointment cancelled', duration: 1800 })).present(); }
          catch (e) { (await this.toasts.create({ message: (e as Error).message, duration: 2500, color: 'danger' })).present(); }
        },
      }],
    });
    await alert.present();
  }
}
