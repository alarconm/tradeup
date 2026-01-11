import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import type { Member } from '../api/auth';
import { getMe, login as apiLogin, logout as apiLogout, signup as apiSignup } from '../api/auth';
import api from '../api/client';

interface AuthContextType {
  member: Member | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (data: { email: string; password: string; name?: string; phone?: string }) => Promise<void>;
  logout: () => void;
  refreshMember: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [member, setMember] = useState<Member | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check if user is already logged in
    if (api.isAuthenticated()) {
      getMe()
        .then((response) => {
          setMember(response.member);
        })
        .catch(() => {
          api.clearTokens();
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const response = await apiLogin(email, password);
    setMember(response.member);
  };

  const signup = async (data: { email: string; password: string; name?: string; phone?: string }) => {
    const response = await apiSignup(data);
    setMember(response.member);
  };

  const logout = () => {
    apiLogout();
    setMember(null);
  };

  const refreshMember = async () => {
    if (api.isAuthenticated()) {
      const response = await getMe();
      setMember(response.member);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        member,
        isLoading,
        isAuthenticated: !!member,
        login,
        signup,
        logout,
        refreshMember,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
