export const en = {
  nav: {
    commandCenter: "Command Center",
    examshieldAi: "EXAMSHIELD AI",
    evidenceCenter: "Evidence Center",
    questionRegistry: "Question Registry",
    threatIntelligence: "Threat Intelligence",
    investigation: "Investigation",
    examLifecycle: "Exam Lifecycle",
    alerts: "Alerts",
    communityAgents: "Community Agents",
    settings: "Settings",
    systemExit: "System Exit",
    operationsGrid: "Operations Grid",
    skipToContent: "Skip to content",
  },
  auth: {
    welcomeBack: "Welcome back",
    signInToContinue: "Sign in to your account to continue",
    createAccount: "Create account",
    signUpToGetStarted: "Sign up to get started with ExamShield",
    email: "Email",
    password: "Password",
    fullName: "Full Name",
    signIn: "Sign In",
    signingIn: "Signing in...",
    signUp: "Sign Up",
    creatingAccount: "Creating account...",
    forgotPassword: "Forgot password?",
    orContinueWith: "Or continue with",
    orSignUpWith: "Or sign up with",
    dontHaveAccount: "Don't have an account?",
    alreadyHaveAccount: "Already have an account?",
    google: "Google",
    github: "GitHub",
  },
  dashboard: {
    commandCenterTitle: "Command Center",
    commandCenterSubtitle: "Real-time overview of national examination security grid.",
  },
} as const;

// `en` is `as const` (literal leaf types) for key-shape autocomplete, but the
// runtime `t()` treats values as `unknown -> string`. Widening leaf values to
// `string` lets non-`as const` locale dictionaries (e.g. `hi`) satisfy the
// type without changing runtime behavior.
type WidenStrings<T> = {
  [K in keyof T]: T[K] extends string ? string : WidenStrings<T[K]>;
};
export type Dictionary = WidenStrings<typeof en>;
