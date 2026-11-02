import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { ApiService } from '../services/api.service';

export const authGuard: CanActivateFn = () => {
  const api = inject(ApiService);
  return api.isLoggedIn() ? true : inject(Router).parseUrl('/login');
};
