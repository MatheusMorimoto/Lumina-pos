import { z } from "zod";

const decimal = z.union([z.number(), z.string()]).transform(String);
const nonNegative = decimal.refine((value) => Number(value) >= 0, "O valor deve ser positivo.");
const positive = decimal.refine((value) => Number(value) > 0, "O valor deve ser maior que zero.");

export const productCreate = z.object({
  store_id: z.uuid(), name: z.string().min(2).max(200), sku: z.string().min(1).max(80),
  barcode: z.string().nullable().optional(), sale_price: nonNegative, tax_amount: nonNegative.default("0"),
  active: z.boolean().default(true),
});
export const productPatch = productCreate.omit({ store_id: true }).partial();
export const batchCreate = z.object({
  lot_number: z.string().min(1), expires_at: z.iso.date().nullable().optional(),
  purchase_price: nonNegative.default("0"), quantity: nonNegative,
});
export const movementCreate = z.object({
  product_id: z.uuid(), batch_id: z.uuid().nullable().optional(),
  type: z.enum(["in", "out", "adjustment", "return"]), quantity: positive,
  unit_cost: decimal.nullable().optional(), reference_type: z.string().nullable().optional(),
  reference_id: z.uuid().nullable().optional(), notes: z.string().nullable().optional(),
});
export const promotionCreate = z.object({
  promotional_price: nonNegative, starts_at: z.iso.datetime({ offset: true }),
  ends_at: z.iso.datetime({ offset: true }), active: z.boolean().default(true),
}).refine((data) => data.ends_at > data.starts_at, { message: "O fim deve ser posterior ao início.", path: ["ends_at"] });
