import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { IonContent, IonSegment, IonSegmentButton, IonLabel, IonSearchbar, IonRefresher, IonRefresherContent, IonButton } from '@ionic/angular';
import { ApiService, Product, Service, peso } from '../../services/api.service';

@Component({
  selector: 'app-shop',
  imports: [FormsModule, IonContent, IonSegment, IonSegmentButton, IonLabel, IonSearchbar, IonRefresher, IonRefresherContent, IonButton],
  template: `
  <ion-content>
    <ion-refresher slot="fixed" (ionRefresh)="refresh($event)"><ion-refresher-content></ion-refresher-content></ion-refresher>
    <div class="page">
      <h1 class="hello">Shop & services</h1>
      <p class="sub">Check prices and live stock before you visit.</p>
      <ion-segment [value]="tab" (ionChange)="setTab($any($event.detail.value))">
        <ion-segment-button value="products"><ion-label>Products</ion-label></ion-segment-button>
        <ion-segment-button value="services"><ion-label>Services</ion-label></ion-segment-button>
      </ion-segment>
      @if (error) { <div class="err">{{ error }}</div> }

      @if (tab === 'products') {
        <ion-searchbar [value]="search" (ionInput)="setSearch($any($event.detail.value))" placeholder="Search products" [debounce]="200"></ion-searchbar>
        <div style="margin-bottom:8px">
          @for (c of categories; track c) { <span class="chip" [class.on]="cat === c" (click)="setCat(c)">{{ c }}</span> }
        </div>
        @for (p of filtered; track p.id) {
          <div class="card row">
            <div class="emoji">{{ p.emoji }}</div>
            <div class="grow"><b>{{ p.name }}</b><div class="sub" style="margin:2px 0 0">{{ p.category }} · {{ money(p.price) }}</div></div>
            <span class="badge" [class.ok]="p.stock > p.reorder_level" [class.low]="p.stock > 0 && p.stock <= p.reorder_level" [class.out]="p.stock === 0">
              {{ p.stock === 0 ? 'Out of stock' : p.stock <= p.reorder_level ? 'Only ' + p.stock + ' left' : 'In stock' }}
            </span>
          </div>
        } @empty { <div class="empty"><span class="big">🔎</span>No products found.</div> }
      } @else {
        @for (s of services; track s.id) {
          <div class="card">
            <div class="row">
              <div class="emoji">{{ s.emoji }}</div>
              <div class="grow"><b>{{ s.name }}</b><div class="sub" style="margin:2px 0 0">{{ s.description }}</div></div>
            </div>
            <div class="row" style="margin-top:10px">
              <div class="grow"><b>{{ money(s.price) }}</b> <span class="sub">· {{ s.duration }} min</span></div>
              <ion-button size="small" (click)="book(s.id)">Book</ion-button>
            </div>
          </div>
        } @empty { <div class="empty">No services available.</div> }
      }
    </div>
  </ion-content>`,
})
export class ShopPage {
  private api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  tab: 'products' | 'services' = 'products';
  products: Product[] = [];
  services: Service[] = [];
  search = ''; cat = 'All'; error = '';
  money = peso;

  get categories() { return ['All', ...Array.from(new Set(this.products.map(p => p.category)))]; }
  get filtered() {
    const s = this.search.trim().toLowerCase();
    return this.products.filter(p => (this.cat === 'All' || p.category === this.cat) && (!s || p.name.toLowerCase().includes(s)));
  }

  private entered = false;
  ngOnInit() { this.entered = true; return this.enter(); }
  ionViewWillEnter() { if (this.entered) { this.entered = false; return; } return this.enter(); }
  private enter() {
    if (this.route.snapshot.queryParamMap.get('tab') === 'services') this.tab = 'services';
    return this.load();
  }
  setTab(v: string) { if (v === 'products' || v === 'services') { this.tab = v; this.cdr.detectChanges(); } }
  setCat(c: string) { this.cat = c; this.cdr.detectChanges(); }
  setSearch(v: string) { this.search = v || ''; this.cdr.detectChanges(); }
  async refresh(ev: CustomEvent) { await this.load(); ev.detail.complete(); }
  book(id: number) { this.router.navigate(['/book'], { queryParams: { service: id } }); }

  private async load() {
    try { await this.loadInner(); } finally { this.cdr.detectChanges(); }
  }

  private async loadInner() {
    this.error = '';
    try { [this.products, this.services] = await Promise.all([this.api.products(), this.api.services()]); }
    catch (e) { this.error = (e as Error).message; }
  }
}
