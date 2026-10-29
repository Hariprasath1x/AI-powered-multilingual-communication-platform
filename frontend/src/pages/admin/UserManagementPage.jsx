import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  Users, 
  Search, 
  ShieldCheck, 
  UserCheck, 
  UserX, 
  ArrowLeft, 
  ChevronLeft, 
  ChevronRight, 
  AlertCircle, 
  CheckCircle2, 
  Loader2 
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { adminService } from '../../services/adminService';

const AVAILABLE_ROLES = ['Admin', 'Campaign Manager', 'Communication Team'];

export default function UserManagementPage() {
  const { user: currentAdmin } = useAuth();

  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [totalPages, setTotalPages] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState('');

  const [isLoading, setIsLoading] = useState(true);
  const [actionInProgress, setActionInProgress] = useState(null); // userId being updated
  const [notification, setNotification] = useState(null); // { type: 'success' | 'error', message: '' }

  const loadUsers = async () => {
    setIsLoading(true);
    const result = await adminService.listUsers({
      page,
      pageSize,
      search: searchTerm,
      role: roleFilter,
    });

    if (result.success) {
      setUsers(result.data.items);
      setTotal(result.data.total);
      setTotalPages(result.data.total_pages);
    } else {
      setNotification({ type: 'error', message: result.error });
    }
    setIsLoading(false);
  };

  useEffect(() => {
    loadUsers();
  }, [page, roleFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    loadUsers();
  };

  const handleRoleChange = async (targetUser, newRole) => {
    if (targetUser.role_name === newRole) return;

    if (targetUser.id === currentAdmin.id && newRole !== 'Admin') {
      setNotification({
        type: 'error',
        message: 'Administrators cannot demote their own account.',
      });
      return;
    }

    setActionInProgress(targetUser.id);
    setNotification(null);

    const result = await adminService.updateUserRole(targetUser.id, newRole);
    if (result.success) {
      setNotification({
        type: 'success',
        message: `Successfully updated ${targetUser.full_name}'s role to ${newRole}.`,
      });
      loadUsers();
    } else {
      setNotification({ type: 'error', message: result.error });
    }
    setActionInProgress(null);
  };

  const handleStatusToggle = async (targetUser) => {
    const newStatus = !targetUser.is_active;

    if (targetUser.id === currentAdmin.id && !newStatus) {
      setNotification({
        type: 'error',
        message: 'Administrators cannot deactivate their own account.',
      });
      return;
    }

    setActionInProgress(targetUser.id);
    setNotification(null);

    const result = await adminService.updateUserStatus(targetUser.id, newStatus);
    if (result.success) {
      setNotification({
        type: 'success',
        message: `User ${targetUser.full_name} is now ${newStatus ? 'Active' : 'Deactivated'}.`,
      });
      loadUsers();
    } else {
      setNotification({ type: 'error', message: result.error });
    }
    setActionInProgress(null);
  };

  const getRoleBadge = (roleName) => {
    switch (roleName) {
      case 'Admin':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'Campaign Manager':
        return 'bg-indigo-100 text-indigo-800 border-indigo-200';
      case 'Communication Team':
      default:
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-6">
      
      {/* Header & Back link */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Link
            to="/dashboard"
            className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-brand-600 transition mb-1"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />
            Back to Dashboard
          </Link>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            User Directory & Role Governance
          </h1>
          <p className="text-sm text-slate-600">
            Administrator portal to manage user access, elevate privileges, and audit accounts.
          </p>
        </div>
      </div>

      {/* Notification Toast */}
      {notification && (
        <div
          className={`p-4 rounded-xl flex items-start gap-3 text-sm ${
            notification.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
              : 'bg-rose-50 text-rose-800 border border-rose-200'
          }`}
        >
          {notification.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-600 mt-0.5" />
          ) : (
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-600 mt-0.5" />
          )}
          <div className="flex-grow font-medium leading-relaxed">{notification.message}</div>
          <button
            onClick={() => setNotification(null)}
            className="text-slate-400 hover:text-slate-600 text-xs font-bold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Search & Filters */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-96">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by name, email, or org..."
            className="block w-full pl-10 pr-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:ring-brand-500 focus:border-brand-500 focus:outline-none focus:ring-2"
          />
        </form>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <label htmlFor="role-filter" className="text-xs font-semibold text-slate-600 uppercase tracking-wider whitespace-nowrap">
            Role:
          </label>
          <select
            id="role-filter"
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value);
              setPage(1);
            }}
            className="block w-full sm:w-48 px-3 py-2 text-sm rounded-xl border border-slate-300 bg-white focus:ring-brand-500 focus:border-brand-500 focus:outline-none focus:ring-2"
          >
            <option value="">All Roles</option>
            {AVAILABLE_ROLES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-8 h-8 text-brand-600 animate-spin" />
            <p className="text-sm text-slate-500">Loading user records...</p>
          </div>
        ) : users.length === 0 ? (
          <div className="py-16 text-center space-y-2">
            <Users className="w-10 h-10 text-slate-300 mx-auto" />
            <p className="text-sm font-semibold text-slate-700">No users found</p>
            <p className="text-xs text-slate-500">Try adjusting your search criteria or role filter.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-6 py-4">User</th>
                  <th scope="col" className="px-6 py-4">Organization</th>
                  <th scope="col" className="px-6 py-4">Role</th>
                  <th scope="col" className="px-6 py-4">Status</th>
                  <th scope="col" className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => {
                  const isCurrent = u.id === currentAdmin?.id;
                  const isBusy = actionInProgress === u.id;

                  return (
                    <tr key={u.id} className="hover:bg-slate-50/80 transition">
                      
                      {/* Name & Email */}
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900 flex items-center gap-2">
                          {u.full_name}
                          {isCurrent && (
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                              You
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-500">{u.email}</div>
                      </td>

                      {/* Organization */}
                      <td className="px-6 py-4 text-slate-600">
                        {u.organization || <span className="text-slate-400 italic">None specified</span>}
                      </td>

                      {/* Role Dropdown */}
                      <td className="px-6 py-4">
                        <select
                          value={u.role_name}
                          disabled={isBusy}
                          onChange={(e) => handleRoleChange(u, e.target.value)}
                          className={`text-xs font-semibold px-2.5 py-1.5 rounded-lg border focus:ring-2 focus:ring-brand-500 focus:outline-none transition ${getRoleBadge(u.role_name)} ${isBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                        >
                          {AVAILABLE_ROLES.map((r) => (
                            <option key={r} value={r}>{r}</option>
                          ))}
                        </select>
                      </td>

                      {/* Active Status Badge */}
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${
                            u.is_active
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : 'bg-rose-50 text-rose-700 border-rose-200'
                          }`}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                          {u.is_active ? 'Active' : 'Deactivated'}
                        </span>
                      </td>

                      {/* Actions Toggle */}
                      <td className="px-6 py-4 text-right">
                        <button
                          type="button"
                          disabled={isBusy || (isCurrent && u.is_active)}
                          onClick={() => handleStatusToggle(u)}
                          className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                            u.is_active
                              ? 'text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 disabled:opacity-40 disabled:cursor-not-allowed'
                              : 'text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 disabled:opacity-40 disabled:cursor-not-allowed'
                          }`}
                          title={isCurrent ? 'You cannot deactivate your own account' : ''}
                        >
                          {isBusy ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : u.is_active ? (
                            <>
                              <UserX className="w-3.5 h-3.5" />
                              Deactivate
                            </>
                          ) : (
                            <>
                              <UserCheck className="w-3.5 h-3.5" />
                              Activate
                            </>
                          )}
                        </button>
                      </td>

                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {total > 0 && (
          <div className="bg-slate-50 px-6 py-4 border-t border-slate-200 flex items-center justify-between text-xs text-slate-600">
            <div>
              Showing <span className="font-semibold">{(page - 1) * pageSize + 1}</span> to{' '}
              <span className="font-semibold">{Math.min(page * pageSize, total)}</span> of{' '}
              <span className="font-semibold">{total}</span> accounts
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1 || isLoading}
                onClick={() => setPage(page - 1)}
                className="p-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="font-medium">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages || isLoading}
                onClick={() => setPage(page + 1)}
                className="p-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

    </div>
  );
}

