import { z } from "zod";

export const digits = (value: string): string => value.replace(/\D/g, "");

export function validCpf(raw: string): boolean {
  const value = digits(raw);
  if (value.length !== 11 || new Set(value).size === 1) return false;
  const numbers = [...value].map(Number);
  for (const size of [9, 10]) {
    const total = numbers.slice(0, size).reduce((sum, number, index) => sum + number * (size + 1 - index), 0);
    const check = 11 - (total % 11);
    if (numbers[size] !== (check >= 10 ? 0 : check)) return false;
  }
  return true;
}

export function validCnpj(raw: string): boolean {
  const value = digits(raw);
  if (value.length !== 14 || new Set(value).size === 1) return false;
  const numbers = [...value].map(Number);
  const cases: Array<[number, number[]]> = [
    [12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]],
    [13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]],
  ];
  for (const [size, weights] of cases) {
    const remainder = numbers.slice(0, size).reduce((sum, number, index) => sum + number * (weights[index] ?? 0), 0) % 11;
    if (numbers[size] !== (remainder < 2 ? 0 : 11 - remainder)) return false;
  }
  return true;
}

const taxRegime = z.enum(["mei", "simples_nacional", "lucro_presumido", "lucro_real", "pessoa_fisica", "nao_informado"]);
const normalizedInput = z.preprocess((raw) => {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return raw;
  const data = { ...(raw as Record<string, unknown>) };
  const address = data.address as Record<string, unknown> | undefined;
  if (address) Object.assign(data, {
    postal_code: data.postal_code ?? address.postal_code, street: data.street ?? address.street,
    address_number: data.address_number ?? address.number, complement: data.complement ?? address.complement,
    neighborhood: data.neighborhood ?? address.district, city: data.city ?? address.city, state: data.state ?? address.state,
  });
  const representative = data.legal_representative as Record<string, unknown> | undefined;
  if (representative) Object.assign(data, {
    legal_representative_name: data.legal_representative_name ?? representative.name,
    legal_representative_cpf: data.legal_representative_cpf ?? representative.cpf,
  });
  data.full_name ??= data.name;
  data.main_cnae_code ??= data.cnae;
  delete data.address; delete data.legal_representative; delete data.name; delete data.cnae;
  return data;
}, z.object({
  person_type: z.enum(["company", "individual"]), email: z.string().transform((v) => v.trim().toLowerCase()).pipe(z.email()),
  password: z.string().min(8).max(128), password_confirmation: z.string().min(8).max(128).optional(),
  phone: z.string().transform(digits).refine((v) => v.length >= 10 && v.length <= 13, "Telefone inválido."),
  postal_code: z.string().transform(digits).refine((v) => v.length === 8, "CEP deve conter 8 dígitos."),
  street: z.string().min(2).max(200), address_number: z.string().min(1).max(30), complement: z.string().max(100).nullable().optional(),
  neighborhood: z.string().min(2).max(100), city: z.string().min(2).max(100),
  state: z.string().transform((v) => v.trim().toUpperCase()).refine((v) => /^[A-Z]{2}$/.test(v), "UF inválida."),
  cnpj: z.string().transform(digits).optional(), legal_name: z.string().max(200).optional(), trade_name: z.string().max(200).optional(),
  state_registration: z.string().optional(), municipal_registration: z.string().optional(), company_size: z.string().optional(),
  main_cnae_code: z.string().optional(), main_cnae_description: z.string().optional(), registration_status: z.string().optional(),
  simples_option: z.boolean().optional(), mei_option: z.boolean().optional(), regime_source: z.string().optional(),
  data_manually_corrected: z.boolean().default(false), manually_reviewed: z.boolean().default(false),
  legal_representative_name: z.string().max(200).optional(), legal_representative_cpf: z.string().transform(digits).optional(),
  social_name: z.string().max(200).optional(), observations: z.string().max(2000).optional(),
  cpf: z.string().transform(digits).optional(), full_name: z.string().max(200).optional(), birth_date: z.iso.date().optional(),
  identity_document: z.string().optional(), tax_regime: taxRegime.default("nao_informado"),
}).strict().superRefine((data, context) => {
  if (data.password_confirmation && data.password !== data.password_confirmation) context.addIssue({ code: "custom", message: "As senhas não coincidem." });
  if (!/[A-Za-z]/.test(data.password) || !/\d/.test(data.password)) context.addIssue({ code: "custom", message: "A senha deve conter letras e números." });
  if (data.person_type === "company") {
    if (!data.cnpj || !validCnpj(data.cnpj)) context.addIssue({ code: "custom", message: "CNPJ inválido.", path: ["cnpj"] });
    if (!data.legal_name || data.legal_name.trim().length < 2) context.addIssue({ code: "custom", message: "Razão social é obrigatória." });
    if (!data.trade_name || data.trade_name.trim().length < 2) context.addIssue({ code: "custom", message: "Nome fantasia é obrigatório." });
    if (!data.legal_representative_name) context.addIssue({ code: "custom", message: "Responsável legal é obrigatório." });
    if (!data.legal_representative_cpf || !validCpf(data.legal_representative_cpf)) context.addIssue({ code: "custom", message: "CPF do responsável legal inválido." });
    if (data.tax_regime === "pessoa_fisica") context.addIssue({ code: "custom", message: "Regime tributário incompatível." });
  } else {
    if (!data.cpf || !validCpf(data.cpf)) context.addIssue({ code: "custom", message: "CPF inválido.", path: ["cpf"] });
    if (!data.full_name || data.full_name.trim().length < 2) context.addIssue({ code: "custom", message: "Nome completo é obrigatório." });
    if (!data.birth_date) context.addIssue({ code: "custom", message: "Data de nascimento é obrigatória." });
    if (data.birth_date && data.birth_date > new Date().toISOString().slice(0, 10)) context.addIssue({ code: "custom", message: "Data de nascimento não pode estar no futuro." });
    if (!["pessoa_fisica", "nao_informado"].includes(data.tax_regime)) context.addIssue({ code: "custom", message: "Regime tributário incompatível." });
  }
}));

export const registrationSchema = normalizedInput;
export type Registration = z.infer<typeof registrationSchema>;
export function publicRegistration(data: Registration): Record<string, unknown> {
  const { email: _, password: __, password_confirmation: ___, ...payload } = data;
  return payload;
}
