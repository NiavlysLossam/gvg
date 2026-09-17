export type UserRole = 'super_admin' | 'event_admin';

export interface User {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AdminUserListItem extends User {
  events_count: number;
}

export interface CreateUserData {
  email: string;
  password: string;
  role?: UserRole;
}

export interface UpdateUserData {
  email?: string;
  role?: UserRole;
  is_active?: boolean;
}

export interface ResetPasswordData {
  new_password: string;
}

