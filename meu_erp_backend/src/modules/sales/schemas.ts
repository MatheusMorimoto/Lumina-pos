import { z } from "zod";
const decimal = z.union([z.number(), z.string()]).transform(String);
const nonNegative = decimal.refine((v) => Number(v) >= 0);
const positive = decimal.refine((v) => Number(v) > 0);

export const saleCreate = z.object({
  store_id: z.uuid(), cash_session_id: z.uuid(), customer_id: z.uuid().nullable().optional(),
  discount: nonNegative.default("0"),
});
export const itemSchema = z.object({
  product_id: z.uuid(), batch_id: z.uuid().nullable().optional(), quantity: positive,
  unit_price: nonNegative, discount: nonNegative.default("0"), tax_amount: nonNegative.default("0"),
});
export const finalizeSchema = z.object({ payments: z.array(z.object({
  method: z.string().min(1), amount: positive, institution_id: z.uuid().nullable().optional(),
  installments: z.number().int().positive().default(1), authorization_code: z.string().nullable().optional(),
  due_date: z.iso.date().nullable().optional(),
})).min(1) });
export const cashOpenSchema = z.object({
  cash_register_id: z.uuid(), user_id: z.uuid(), opening_amount: nonNegative.default("0"),
});
export const cashCloseSchema = z.object({ declared_amount: nonNegative });
