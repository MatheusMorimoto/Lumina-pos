import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().transform((value) => value.trim().toLowerCase()).pipe(z.email()),
  password: z.string().min(1),
  store_id: z.string().optional(),
});

export const emailSchema = z.object({ email: z.string().transform((value) => value.trim().toLowerCase()).pipe(z.email()) });

export const passwordSchema = z.object({
  password: z.string().min(8).max(128).refine((value) => /[A-Za-z]/.test(value) && /\d/.test(value), "A senha deve conter letras e números."),
  password_confirmation: z.string().min(8).max(128),
}).refine((value) => value.password === value.password_confirmation, {
  message: "As senhas não coincidem.", path: ["password_confirmation"],
});

export type CurrentUser = {
  id: string;
  email: string | null;
  name: string | null;
  phone: string | null;
  role: string | null;
  store: unknown;
  store_id: string | null;
  registration_complete: boolean;
  profile_found: boolean;
};
