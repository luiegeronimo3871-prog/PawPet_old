import { Component, inject } from '@angular/core';
import { IonTabs, IonTabBar, IonTabButton, IonIcon, IonLabel, IonBadge } from '@ionic/angular';
import { addIcons } from 'ionicons';
import { homeOutline, storefrontOutline, calendarOutline, notificationsOutline, personOutline } from 'ionicons/icons';
import { ApiService } from '../services/api.service';

@Component({
  selector: 'app-tabs',
  imports: [IonTabs, IonTabBar, IonTabButton, IonIcon, IonLabel, IonBadge],
  template: `
  <ion-tabs>
    <ion-tab-bar slot="bottom">
      <ion-tab-button tab="home"><ion-icon name="home-outline"></ion-icon><ion-label>Home</ion-label></ion-tab-button>
      <ion-tab-button tab="shop"><ion-icon name="storefront-outline"></ion-icon><ion-label>Shop</ion-label></ion-tab-button>
      <ion-tab-button tab="appointments"><ion-icon name="calendar-outline"></ion-icon><ion-label>Visits</ion-label></ion-tab-button>
      <ion-tab-button tab="notifications">
        <ion-icon name="notifications-outline"></ion-icon><ion-label>Alerts</ion-label>
        @if (api.unread() > 0) { <ion-badge color="secondary">{{ api.unread() }}</ion-badge> }
      </ion-tab-button>
      <ion-tab-button tab="profile"><ion-icon name="person-outline"></ion-icon><ion-label>Profile</ion-label></ion-tab-button>
    </ion-tab-bar>
  </ion-tabs>`,
})
export class TabsPage {
  api = inject(ApiService);
  constructor() {
    addIcons({ homeOutline, storefrontOutline, calendarOutline, notificationsOutline, personOutline });
  }
}
