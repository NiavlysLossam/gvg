import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  User as UserIcon,
  PlusCircle,
  Search,
  KeyRound,
  Loader2,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  X,
  ArrowLeft,
  UserX,
  UserCheck,
  Calendar,
  Layers,
} from 'lucide-react';
import { AdminUserListItem, CreateUserData, ResetPasswordData } from '../types/auth';
import {
  fetchAdminUsers,
  createAdminUser,
  updateAdminUser,
  resetAdminUserPassword,
} from '../lib/api';
import { useAuth } from '../contexts/AuthContext';

interface AdminUsersPageProps {
  onBack: () => void;
}

export const AdminUsersPage: React.FC<AdminUsersPageProps> = ({ onBack }) => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notification, setNotification] = useState<string | null>(null);

  // Modals state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [resetPasswordTarget, setResetPasswordTarget] = useState<AdminUserListItem | null>(null);

  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAdminUsers();
      setUsers(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors du chargement des utilisateurs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const showNotification = (msg: string) => {
    setNotification(msg);
    setTimeout(() => setNotification(null), 5000);
  };

  const handleToggleActive = async (targetUser: AdminUserListItem) => {
    if (currentUser?.id === targetUser.id) {
      alert('Vous ne pouvez pas désactiver votre propre compte');
      return;
    }

    try {
      const updated = await updateAdminUser(targetUser.id, {
        is_active: !targetUser.is_active,
      });
      setUsers(users.map((u) => (u.id === updated.id ? updated : u)));
      showNotification(
        `Le compte ${updated.email} est désormais ${updated.is_active ? 'activé' : 'désactivé'}.`
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la modification du statut');
    }
  };

  const handleChangeRole = async (targetUser: AdminUserListItem) => {
    if (currentUser?.id === targetUser.id) {
      alert('Vous ne pouvez pas modifier votre propre rôle');
      return;
    }

    const newRole = targetUser.role === 'super_admin' ? 'event_admin' : 'super_admin';
    const roleLabel = newRole === 'super_admin' ? 'Super-Admin' : 'Organisateur';

    if (
      !window.confirm(
        `Confirmez-vous le passage du rôle de ${targetUser.email} à « ${roleLabel} » ?`
      )
    ) {
      return;
    }

    try {
      const updated = await updateAdminUser(targetUser.id, { role: newRole });
      setUsers(users.map((u) => (u.id === updated.id ? updated : u)));
      showNotification(`Le rôle de ${updated.email} a été mis à jour vers « ${roleLabel} ».`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors du changement de rôle');
    }
  };

  const filteredUsers = users.filter((u) =>
    u.email.toLowerCase().includes(searchQuery.trim().toLowerCase())
  );

  const superAdminsCount = users.filter((u) => u.role === 'super_admin').length;
  const organizersCount = users.filter((u) => u.role === 'event_admin').length;
  const activeCount = users.filter((u) => u.is_active).length;

  return (
    <div className="space-y-6">
      {/* Top Banner / Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onBack}
              className="p-2 text-gray-500 hover:text-gray-900 rounded-lg hover:bg-gray-100 transition"
              title="Retour aux événements"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="p-2.5 bg-purple-100 text-purple-700 rounded-xl">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-2xl font-extrabold text-gray-900">
                Console Super-Admin &mdash; Utilisateurs
              </h2>
              <p className="text-sm text-gray-500">
                Gérez les comptes organisateurs, les privilèges d'accès et réinitialisez les mots de passe.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={loadUsers}
            disabled={loading}
            className="p-2.5 text-gray-500 hover:text-gray-700 rounded-xl hover:bg-gray-100 border border-gray-200 transition"
            title="Actualiser la liste"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            type="button"
            onClick={() => setIsCreateOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white text-sm font-semibold rounded-xl shadow-xs transition"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Nouvel Utilisateur</span>
          </button>
        </div>
      </div>

      {/* Notifications and Alerts */}
      {notification && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-3 rounded-xl flex items-center justify-between shadow-xs animate-fade-in">
          <div className="flex items-center space-x-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <p className="text-sm font-medium">{notification}</p>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-xs text-emerald-700 hover:underline font-semibold"
          >
            Fermer
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-xl flex items-center justify-between shadow-xs">
          <div className="flex items-center space-x-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <p className="text-sm font-medium">{error}</p>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-xs text-red-700 hover:underline font-semibold"
          >
            Fermer
          </button>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-2xs">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Total Comptes
          </p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{users.length}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-2xs">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Organisateurs
          </p>
          <p className="text-2xl font-bold text-blue-600 mt-1">{organizersCount}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-2xs">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Super-Admins
          </p>
          <p className="text-2xl font-bold text-purple-600 mt-1">{superAdminsCount}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-2xs">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Actifs / Total
          </p>
          <p className="text-2xl font-bold text-emerald-600 mt-1">
            {activeCount} / {users.length}
          </p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-2xs flex items-center gap-3">
        <Search className="w-5 h-5 text-gray-400 flex-shrink-0" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Rechercher par adresse e-mail..."
          className="w-full text-sm outline-hidden text-gray-800 placeholder-gray-400"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => setSearchQuery('')}
            className="text-xs text-gray-400 hover:text-gray-600"
          >
            Effacer
          </button>
        )}
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-2xs overflow-hidden">
        {loading && users.length === 0 ? (
          <div className="py-16 text-center text-gray-500">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-3 text-purple-600" />
            <p className="text-sm font-medium">Chargement des utilisateurs...</p>
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="py-16 text-center text-gray-500">
            <UserIcon className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-base font-semibold text-gray-700">Aucun utilisateur trouvé</p>
            <p className="text-xs text-gray-400 mt-1">
              {searchQuery
                ? 'Aucun compte ne correspond à votre recherche.'
                : 'Commencez par créer un compte organisateur.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 text-xs font-semibold uppercase text-gray-500 border-b border-gray-200">
                <tr>
                  <th className="py-3.5 px-4">Utilisateur</th>
                  <th className="py-3.5 px-4">Rôle</th>
                  <th className="py-3.5 px-4">Statut</th>
                  <th className="py-3.5 px-4 text-center">Événements</th>
                  <th className="py-3.5 px-4">Créé le</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredUsers.map((user) => {
                  const isSelf = currentUser?.id === user.id;
                  const createdDate = new Date(user.created_at).toLocaleDateString('fr-FR', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                  });

                  return (
                    <tr key={user.id} className="hover:bg-gray-50/70 transition">
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center font-semibold text-xs flex-shrink-0">
                            {user.email.substring(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-semibold text-gray-900 flex items-center gap-1.5">
                              <span>{user.email}</span>
                              {isSelf && (
                                <span className="text-2xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-full font-bold">
                                  Vous
                                </span>
                              )}
                            </div>
                            <div className="text-2xs text-gray-400 font-mono">{user.id}</div>
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${
                            user.role === 'super_admin'
                              ? 'bg-purple-50 text-purple-700 border border-purple-200'
                              : 'bg-blue-50 text-blue-700 border border-blue-200'
                          }`}
                        >
                          {user.role === 'super_admin' ? (
                            <ShieldCheck className="w-3.5 h-3.5 text-purple-600" />
                          ) : (
                            <UserIcon className="w-3.5 h-3.5 text-blue-600" />
                          )}
                          <span>{user.role === 'super_admin' ? 'Super-Admin' : 'Organisateur'}</span>
                        </span>
                      </td>

                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            user.is_active
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-gray-100 text-gray-600 border border-gray-200'
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              user.is_active ? 'bg-emerald-500' : 'bg-gray-400'
                            }`}
                          />
                          <span>{user.is_active ? 'Actif' : 'Désactivé'}</span>
                        </span>
                      </td>

                      <td className="py-3.5 px-4 text-center">
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-gray-100 text-gray-800">
                          <Layers className="w-3 h-3 text-gray-500" />
                          <span>{user.events_count ?? 0}</span>
                        </span>
                      </td>

                      <td className="py-3.5 px-4 text-xs text-gray-500">
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5 text-gray-400" />
                          <span>{createdDate}</span>
                        </div>
                      </td>

                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Reset Password */}
                          <button
                            type="button"
                            onClick={() => setResetPasswordTarget(user)}
                            className="p-1.5 text-gray-500 hover:text-purple-700 hover:bg-purple-50 rounded-lg transition"
                            title="Réinitialiser le mot de passe"
                          >
                            <KeyRound className="w-4 h-4" />
                          </button>

                          {/* Role toggle (not self) */}
                          {!isSelf && (
                            <button
                              type="button"
                              onClick={() => handleChangeRole(user)}
                              className="px-2 py-1 text-2xs font-semibold text-gray-600 hover:text-purple-700 hover:bg-purple-50 border border-gray-200 rounded-lg transition"
                              title="Basculer le rôle"
                            >
                              {user.role === 'super_admin' ? 'Rétrograder' : 'Promouvoir'}
                            </button>
                          )}

                          {/* Activate / Deactivate (not self) */}
                          {!isSelf && (
                            <button
                              type="button"
                              onClick={() => handleToggleActive(user)}
                              className={`p-1.5 rounded-lg transition ${
                                user.is_active
                                  ? 'text-gray-400 hover:text-red-600 hover:bg-red-50'
                                  : 'text-emerald-600 hover:bg-emerald-50'
                              }`}
                              title={user.is_active ? 'Désactiver le compte' : 'Activer le compte'}
                            >
                              {user.is_active ? (
                                <UserX className="w-4 h-4" />
                              ) : (
                                <UserCheck className="w-4 h-4" />
                              )}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create User Modal */}
      {isCreateOpen && (
        <CreateUserModal
          isOpen={isCreateOpen}
          onClose={() => setIsCreateOpen(false)}
          onSuccess={(created) => {
            setUsers([created, ...users]);
            showNotification(`L'utilisateur ${created.email} a été créé avec succès.`);
            setIsCreateOpen(false);
          }}
        />
      )}

      {/* Reset Password Modal */}
      {resetPasswordTarget && (
        <ResetPasswordModal
          user={resetPasswordTarget}
          isOpen={Boolean(resetPasswordTarget)}
          onClose={() => setResetPasswordTarget(null)}
          onSuccess={() => {
            showNotification(
              `Le mot de passe de ${resetPasswordTarget.email} a été réinitialisé.`
            );
            setResetPasswordTarget(null);
          }}
        />
      )}
    </div>
  );
};

// Sub-component: Create User Modal
interface CreateUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: AdminUserListItem) => void;
}

const CreateUserModal: React.FC<CreateUserModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'event_admin' | 'super_admin'>('event_admin');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload: CreateUserData = {
        email: email.trim().toLowerCase(),
        password,
        role,
      };
      const created = await createAdminUser(payload);
      onSuccess(created);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors de la création de l'utilisateur");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100 relative animate-in fade-in zoom-in duration-200">
        <button
          type="button"
          onClick={onClose}
          disabled={loading}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100 transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="p-2.5 bg-purple-100 text-purple-700 rounded-xl">
            <PlusCircle className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900">Créer un nouvel utilisateur</h3>
            <p className="text-xs text-gray-500">Ajouter un compte administrateur ou organisateur</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              Adresse e-mail :
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="organisateur@exemple.fr"
              className="w-full px-3.5 py-2.5 text-sm border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-hidden transition"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              Mot de passe temporaire :
            </label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Au moins 6 caractères"
              className="w-full px-3.5 py-2.5 text-sm border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-hidden transition"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">Rôle :</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as 'event_admin' | 'super_admin')}
              className="w-full px-3.5 py-2.5 text-sm border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-hidden transition bg-white"
              disabled={loading}
            >
              <option value="event_admin">Organisateur (Accès à ses propres événements)</option>
              <option value="super_admin">Super-Admin (Accès global et gestion des comptes)</option>
            </select>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-xl transition"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-purple-600 hover:bg-purple-700 disabled:bg-purple-300 rounded-xl shadow-xs transition"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              <span>Créer l'utilisateur</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// Sub-component: Reset Password Modal
interface ResetPasswordModalProps {
  user: AdminUserListItem;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const ResetPasswordModal: React.FC<ResetPasswordModalProps> = ({
  user,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [newPassword, setNewPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 6) {
      setError('Le mot de passe doit comporter au moins 6 caractères');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload: ResetPasswordData = { new_password: newPassword };
      await resetAdminUserPassword(user.id, payload);
      onSuccess();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Erreur lors de la réinitialisation du mot de passe'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100 relative animate-in fade-in zoom-in duration-200">
        <button
          type="button"
          onClick={onClose}
          disabled={loading}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100 transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="p-2.5 bg-purple-100 text-purple-700 rounded-xl">
            <KeyRound className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900">Réinitialiser le mot de passe</h3>
            <p className="text-xs text-gray-500 truncate max-w-[280px]">{user.email}</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              Nouveau mot de passe :
            </label>
            <input
              type="password"
              required
              minLength={6}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Minimum 6 caractères"
              className="w-full px-3.5 py-2.5 text-sm border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-hidden transition"
              disabled={loading}
              autoFocus
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-3">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-xl transition"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={loading || newPassword.length < 6}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-purple-600 hover:bg-purple-700 disabled:bg-purple-300 rounded-xl shadow-xs transition"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              <span>Enregistrer</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

