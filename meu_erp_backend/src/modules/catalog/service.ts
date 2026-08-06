import { Decimal } from "decimal.js";
import { BusinessRuleError, NotFoundError } from "../../core/errors.ts";

export function decreaseBatchBalance(batch: { quantity?: Decimal.Value; saldo?: Decimal.Value } | null, requested: Decimal.Value): Decimal {
  if (!batch) throw new NotFoundError("Lote não encontrado.");
  const balance = new Decimal(batch.quantity ?? batch.saldo ?? 0); const quantity = new Decimal(requested);
  if (quantity.greaterThan(balance)) throw new BusinessRuleError("Saldo insuficiente no lote.");
  return balance.minus(quantity);
}
export function validateExpiryWindow(days: number): void {
  if (!Number.isInteger(days) || days < 0 || days > 365) throw new BusinessRuleError("O período deve estar entre 0 e 365 dias.");
}
