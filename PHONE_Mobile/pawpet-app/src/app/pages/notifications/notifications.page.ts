import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { IonContent, IonRefresher, IonRefresherContent } from '@ionic/angular';
import { ApiService, AppNotification } from '../../services/api.service';

@Component({
  selector: 'app-notifications',
  imports: [IonContent, IonRefresher, IonRefresherContent],
  template: `
  <ion-content>
    <ion-refresher slot="fixed" (ionRefresh)="refresh($event)"><ion-refresher-content></ion-refresher-content></ion-refresher>
    <div class="page">
      <h1 class="hello">Alerts</h1>
      <p class="sub">Confirmations and reminders from the clinic.</p>
      @if (error) { <div class="err">{{ error }}</div> }
      @for (n of items; track n.id) {
        <div class="card" [style.border-color]="n.is_read ? '' : '#ff8a4c'">
          <div class="row"><div class="avatar">🔔</div>
            <div class="grow"><b>{{ n.title }}</b><div class="sub" style="margin:2px 0 0">{{ n.body }}</div>
              <small style="color:var(--pp-muted)">{{ n.created_at.slice(0, 16) }}</small></div></div>
        </div>
      } @empty { <div class="empty"><span class="big">🔕</span>No notifications yet.</div> }
    </div>
  </ion-content>`,
})
export class NotificationsPage {
  private api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);
  items: AppNotification[] = [];
  error = '';

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
      this.items = await this.api.notifications();
      if (this.items.some(n => !n.is_read)) {
        // keep the orange "unread" highlight for this visit, clear the badge on the server
        await this.api.markRead();
      }
    } catch (e) { this.error = (e as Error).message; }
  }
}
