import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom, Observable, TimeoutError, timeout } from 'rxjs';
import { API_URL } from '../config';

export interface User { id: number; username: string; full_name: string; email: string; phone: string; role: string; must_change?: boolean; }
export interface Pet { id: number; owner_id: number; name: string; species: string; breed: string; age: number | null; weight: number | null; notes: string; }
export interface Product { id: number; name: string; category: string; price: number; stock: number; reorder_level: number; emoji: string; }
export interface Service { id: number; name: string; description: string; price: number; duration: number; emoji: string; }
export interface Vet { id: number; name: string; specialty: string; work_days: string; start_time: string; end_time: string; }
export interface Slot { time: string; available: boolean; }
export interface Appointment {
  id: number; appt_date: string; appt_time: string; status: string; notes: string;
  pet_name: string; species: string; service_name: string; service_price: number; service_emoji: string; vet_name: string;
}
export interface AppNotification { id: number; title: string; body: string; is_read: number; created_at: string; }

const REQUEST_TIMEOUT_MS = 15000;   // a stuck connection shows an error instead of spinning forever

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  user = signal<User | null>(JSON.parse(localStorage.getItem('pp_user') || 'null'));
  unread = signal(0);

  get token(): string { return localStorage.getItem('pp_token') || ''; }
  isLoggedIn(): boolean { return !!this.token; }

  private async call<T>(req: Observable<T>): Promise<T> {
    try {
      return await firstValueFrom(req.pipe(timeout(REQUEST_TIMEOUT_MS)));
    } catch (e) {
      if (e instanceof TimeoutError || (e as Error)?.name === 'TimeoutError') {
        throw new Error('The server is taking too long to answer. Check your connection and try again.');
      }
      const err = e as HttpErrorResponse;
      if (err.status === 0) throw new Error('Cannot reach the PawPet server. Check your connection and the server address.');
      if (err.status === 413) throw new Error('That is too much text. Please shorten it.');
      if (err.status === 429 && !err.error?.error) throw new Error('Too many attempts. Please wait a few minutes and try again.');
      throw new Error(err.error?.error || 'Something went wrong. Please try again.');
    }
  }

  // ---- auth
  async login(username: string, password: string) {
    const r = await this.call(this.http.post<{ token: string; user: User }>(`${API_URL}/login`, { username, password }));
    localStorage.setItem('pp_token', r.token);
    localStorage.setItem('pp_user', JSON.stringify(r.user));
    this.user.set(r.user);
  }
  register(body: { full_name: string; username: string; password: string; email: string; phone: string }) {
    return this.call(this.http.post(`${API_URL}/register`, body));
  }
  async changePassword(oldPassword: string, newPassword: string) {
    await this.call(this.http.post(`${API_URL}/change-password`, { old_password: oldPassword, new_password: newPassword }));
    const u = this.user();
    if (u) { u.must_change = false; localStorage.setItem('pp_user', JSON.stringify(u)); this.user.set({ ...u }); }
  }
  /** Forget everything and reload the app, so the next person never sees the previous person's data. */
  hardReset() {
    this.clearSession();
    window.location.replace(new URL('login', document.baseURI).toString());
  }
  clearSession() {
    localStorage.removeItem('pp_token');
    localStorage.removeItem('pp_user');
    this.user.set(null);
    this.unread.set(0);
  }
  async logout() {
    try { await this.call(this.http.post(`${API_URL}/logout`, {})); } catch { /* ignore */ }
    this.clearSession();
  }

  // ---- catalog
  products(q = '') { return this.call(this.http.get<Product[]>(`${API_URL}/products`, { params: q ? { q } : {} })); }
  services() { return this.call(this.http.get<Service[]>(`${API_URL}/services`)); }
  vets() { return this.call(this.http.get<Vet[]>(`${API_URL}/vets`)); }
  availability(vetId: number, serviceId: number, date: string) {
    return this.call(this.http.get<Slot[]>(`${API_URL}/availability`, { params: { vet_id: vetId, service_id: serviceId, date } }));
  }

  // ---- pets
  pets() { return this.call(this.http.get<Pet[]>(`${API_URL}/pets`)); }
  addPet(p: Partial<Pet>) { return this.call(this.http.post(`${API_URL}/pets`, p)); }
  deletePet(id: number) { return this.call(this.http.delete(`${API_URL}/pets/${id}`)); }

  // ---- appointments
  appointments() { return this.call(this.http.get<Appointment[]>(`${API_URL}/appointments`)); }
  book(body: { pet_id: number; service_id: number; vet_id: number; appt_date: string; appt_time: string; notes: string }) {
    return this.call(this.http.post<{ id: number }>(`${API_URL}/appointments`, body));
  }
  cancel(id: number) { return this.call(this.http.post(`${API_URL}/appointments/${id}/cancel`, {})); }

  // ---- notifications
  async notifications() {
    const l = await this.call(this.http.get<AppNotification[]>(`${API_URL}/notifications`));
    this.unread.set(l.filter(n => !n.is_read).length);
    return l;
  }
  async markRead() {
    await this.call(this.http.post(`${API_URL}/notifications/read`, {}));
    this.unread.set(0);
  }
}

// ---- small helpers shared by pages
export function localDate(d: Date): string {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
export function t12(t: string): string {
  const [h, m] = t.split(':').map(Number);
  return ((h + 11) % 12 + 1) + ':' + String(m).padStart(2, '0') + ' ' + (h >= 12 ? 'PM' : 'AM');
}
export function peso(n: number): string {
  return '₱' + Number(n || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
export function prettyDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

export function passwordProblem(p: string): string {
  if (p.length < 8) return 'Password must be at least 8 characters.';
  if (p.length > 128) return 'Password is too long.';
  if (!/[A-Za-z]/.test(p) || !/\d/.test(p)) return 'Password needs at least one letter and one number.';
  if (['admin123', 'staff123', 'pass123'].includes(p)) return 'Choose a password that is not a common or default one.';
  return '';
}
