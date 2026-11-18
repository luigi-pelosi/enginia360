// Regole condivise dal cambio obbligatorio, dal reset amministrativo e dal profilo.
export function passwordValidation(password: string, confirm: string): "passwordMismatch" | "passwordMinimum" | "passwordBlank" | "" {
  if (!password.trim()) return "passwordBlank";
  if (password !== confirm) return "passwordMismatch";
  if ([...password].length < 14) return "passwordMinimum";
  return "";
}
