import React from 'react';
import { LogOut, ShieldCheck, User as UserIcon } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

interface AdminHeaderProps {
  onLogout?: () => void;
  onNavigateUsers?: () => void;
}

export const AdminHeader: React.FC<AdminHeaderProps> = ({ onLogout, onNavigateUsers }) => {
  const { user, logout } = useAuth();

  if (!user) return null;

  const isSuperAdmin = user.role === 'super_admin';

  const handleLogout = () => {
    logout();
    if (onLogout) {
      onLogout();
    }
  };

  return (
    <div className="flex items-center space-x-3 text-sm">
      <div className="hidden sm:flex items-center space-x-2 pl-3 border-l border-gray-200">
        {isSuperAdmin && onNavigateUsers ? (
          <button
            type="button"
            onClick={onNavigateUsers}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold shadow-2xs bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 transition cursor-pointer"
            title="Accéder à la gestion des utilisateurs (Super-Admin)"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-purple-600" />
            <span>Super-Admin</span>
          </button>
        ) : (
          <span
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold shadow-2xs ${
              isSuperAdmin
                ? 'bg-purple-50 text-purple-700 border border-purple-200'
                : 'bg-blue-50 text-blue-700 border border-blue-200'
            }`}
            title={isSuperAdmin ? 'Accès administrateur global' : 'Gestion limitée à vos événements'}
          >
            {isSuperAdmin ? (
              <ShieldCheck className="w-3.5 h-3.5 text-purple-600" />
            ) : (
              <UserIcon className="w-3.5 h-3.5 text-blue-600" />
            )}
            <span>{isSuperAdmin ? 'Super-Admin' : 'Organisateur'}</span>
          </span>
        )}

        <span className="text-gray-700 font-medium truncate max-w-[200px]" title={user.email}>
          {user.email}
        </span>
      </div>

      <button
        onClick={handleLogout}
        className="p-2 sm:px-3 sm:py-1.5 rounded-lg text-xs font-semibold text-gray-600 hover:text-red-700 hover:bg-red-50 border border-transparent hover:border-red-200 transition flex items-center gap-1.5"
        title="Se déconnecter"
      >
        <LogOut className="w-4 h-4 text-gray-500 hover:text-red-600" />
        <span className="hidden sm:inline">Déconnexion</span>
      </button>
    </div>
  );
};

