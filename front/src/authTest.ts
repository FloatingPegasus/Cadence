import { vi } from "vitest";

import type { AuthContextValue, AuthUser } from "./contexts/AuthContext";

export const testUser: AuthUser = {
  id: 1,
  username: "alpha",
  email: "alpha@example.com",
  is_verified: true,
  is_guest: false,
  is_developer: false,
  ai_processing_consent: false,
  ai_redaction_enabled: true,
  day_ends_at: 0,
  auto_close: true,
  about: "",
};

export function authStub(
  overrides: Partial<AuthContextValue> = {},
): AuthContextValue {
  return {
    user: testUser,
    isLoading: false,
    allowGuests: false,
    aiEnabled: false,
    authDialog: null,
    login: vi.fn(),
    register: vi.fn(),
    claim: vi.fn(),
    ensureSession: vi.fn(),
    openLogin: vi.fn(),
    openClaim: vi.fn(),
    closeAuth: vi.fn(),
    resendVerification: vi.fn(),
    updateAIPrivacy: vi.fn(),
    updateDaySettings: vi.fn(),
    updateAbout: vi.fn(),
    verifyEmail: vi.fn(),
    logout: vi.fn(),
    ...overrides,
  };
}
