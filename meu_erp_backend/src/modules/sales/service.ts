import { Decimal } from "decimal.js";
import { BusinessRuleError, NotFoundError } from "../../core/errors.ts";

export type SaleItem = { quantity: Decimal.Value; unitPrice: Decimal.Value; discount?: Decimal.Value };
export function calculateSaleTotal(items: SaleItem[]): Decimal {
  const total = items.reduce((sum, item) => sum.plus(new Decimal(item.quantity).times(item.unitPrice).minus(item.discount ?? 0)), new Decimal(0));
  if (total.isNegative()) throw new BusinessRuleError("O desconto não pode superar o valor da venda.");
  return total;
}
export function requireOpenCash(cash: { status: string } | null): void {
  if (!cash) throw new NotFoundError("Caixa não encontrado.");
  if (cash.status !== "aberto" && cash.status !== "open") throw new BusinessRuleError("Não é possível vender com o caixa fechado.");
}
export function calculateCashDifference(opening: Decimal.Value, moved: Decimal.Value, declared: Decimal.Value) {
  const expected = new Decimal(opening).plus(moved); const difference = new Decimal(declared).minus(expected);
  return { expected, difference };
}
