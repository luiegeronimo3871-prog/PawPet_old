import { Routes } from '@angular/router';
import { authGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: 'tabs/home', pathMatch: 'full' },
  { path: 'login', loadComponent: () => import('./pages/login/login.page').then(m => m.LoginPage) },
  { path: 'book', canActivate: [authGuard], loadComponent: () => import('./pages/book/book.page').then(m => m.BookPage) },
  {
    path: 'tabs',
    canActivate: [authGuard],
    loadComponent: () => import('./tabs/tabs.page').then(m => m.TabsPage),
    children: [
      { path: 'home', loadComponent: () => import('./pages/home/home.page').then(m => m.HomePage) },
      { path: 'shop', loadComponent: () => import('./pages/shop/shop.page').then(m => m.ShopPage) },
      { path: 'appointments', loadComponent: () => import('./pages/appointments/appointments.page').then(m => m.AppointmentsPage) },
      { path: 'notifications', loadComponent: () => import('./pages/notifications/notifications.page').then(m => m.NotificationsPage) },
      { path: 'profile', loadComponent: () => import('./pages/profile/profile.page').then(m => m.ProfilePage) },
      { path: '', redirectTo: 'home', pathMatch: 'full' },
    ],
  },
  { path: '**', redirectTo: 'tabs/home' },
];
