import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { IonContent, IonRefresher, IonRefresherContent, IonButton } from '@ionic/angular';
import { ApiService, Appointment, Pet, Product, localDate, t12, prettyDate, peso } from '../../services/api.service';

@Component({
  selector: 'app-home',
  imports: [RouterLink, IonContent, IonRefresher, IonRefresherContent, IonButton],
  template: `
  <ion-content>
    <ion-refresher slot="fixed" (ionRefresh)="refresh($event)"><ion-refresher-content></ion-refresher-content></ion-refresher>
    <div class="page">
      <div class="row">
        <div class="grow">
          <h1 class="hello">{{ greeting }},<br>{{ firstName }}</h1>
          <p class="sub">How can we help today?</p>
        </div>
        <div class="faces">
          @for (p of pets.slice(0, 3); track p.id) { <div class="avatar">{{ p.species === 'Cat' ? '🐱' : '🐶' }}</div> }
        </div>
      </div>

      @if (error) { <div class="err">{{ error }}</div> }

      @if (next) {
        <div class="hero-card">
          <div class="row">
            <div class="grow">
              <div>{{ next.pet_name }}'s visit<br>{{ next.service_name }} with {{ next.vet_name }}</div>
              <div class="when">{{ date(next.appt_date) }} · {{ time(next.appt_time) }}</div>
              <a class="link" routerLink="/tabs/appointments">View appointment ›</a>
            </div>
            <div class="datebox"><small>{{ month(next.appt_date) }}</small><b>{{ day(next.appt_date) }}</b></div>
          </div>
        </div>
      } @else {
        <div class="hero-card">
          <div>No upcoming visits</div>
          <div class="when">Book your pet's next checkup</div>
        </div>
      }
      <div class="row" style="margin-top:12px">
        <ion-button class="pp grow" routerLink="/book">＋ Book new</ion-button>
        <ion-button class="pp grow" fill="outline" routerLink="/tabs/appointments">History</ion-button>
      </div>

      <h3 class="sec">What do you need?</h3>
      <div class="row" style="align-items:stretch">
        <a class="tile grow" routerLink="/tabs/shop"><b>Shop</b><span>Food, meds & more ›</span><span class="big">🛍️</span></a>
        <a class="tile grow" (click)="goServices()"><b>Services</b><span>Checkups, grooming ›</span><span class="big">🩺</span></a>
      </div>

      <h3 class="sec">Your pets</h3>
      @if (pets.length) {
        @for (p of pets; track p.id) {
          <div class="card row">
            <div class="avatar">{{ p.species === 'Cat' ? '🐱' : '🐶' }}</div>
            <div class="grow"><b>{{ p.name }}</b><div class="sub" style="margin:0">{{ p.breed || p.species }}@if (p.age) {, {{ p.age }} yr}</div></div>
          </div>
        }
      } @else {
        <div class="card empty">Add your pet in the Profile tab so you can book visits.</div>
      }

      <h3 class="sec">Running low in the shop</h3>
      @for (p of lowStock; track p.id) {
        <div class="card row"><div class="emoji">{{ p.emoji }}</div><div class="grow"><b>{{ p.name }}</b><div class="sub" style="margin:0">{{ money(p.price) }}</div></div>
          <span class="badge" [class.out]="p.stock === 0" [class.low]="p.stock > 0">{{ p.stock === 0 ? 'Out of stock' : 'Only ' + p.stock + ' left' }}</span></div>
      } @empty { <div class="card empty">All items are well stocked.</div> }
    </div>
  </ion-content>`,
  styles: [`.faces { display: flex; gap: -8px; } .faces .avatar { margin-left: -10px; border: 2px solid #fff; } a.tile { text-decoration: none; }`],
})
export class HomePage {
  private api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);
  private router = inject(Router);
  next: Appointment | null = null;
  pets: Pet[] = [];
  lowStock: Product[] = [];
  error = '';

  get firstName() { return (this.api.user()?.full_name || '').split(' ')[0]; }
  get greeting() { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'; }
  date = prettyDate; time = t12; money = peso;
  month(d: string) { return new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short' }); }
  day(d: string) { return new Date(d + 'T00:00:00').getDate(); }
  goServices() { this.router.navigate(['/tabs/shop'], { queryParams: { tab: 'services' } }); }

  private entered = false;
  ngOnInit() { this.entered = true; return this.load(); }
  ionViewWillEnter() { if (this.entered) { this.entered = false; return; } return this.load(); }
  async refresh(ev: CustomEvent) { await this.load(); ev.detail.complete(); }

  private async load() {
    try { await this.loadInner(); } finally { this.cdr.detectChanges(); }
  }

  private async loadInner() {
    this.error = '';
    try {
      const [appts, pets, products] = await Promise.all([this.api.appointments(), this.api.pets(), this.api.products()]);
      const today = localDate(new Date());
      this.next = appts.filter(a => ['pending', 'confirmed'].includes(a.status) && a.appt_date >= today)
        .sort((a, b) => (a.appt_date + a.appt_time).localeCompare(b.appt_date + b.appt_time))[0] || null;
      this.pets = pets;
      this.lowStock = products.filter(p => p.stock <= p.reorder_level).slice(0, 3);
      this.api.notifications().catch(() => undefined);
    } catch (e) { this.error = (e as Error).message; }
  }
}
