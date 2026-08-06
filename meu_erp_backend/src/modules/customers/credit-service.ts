import { Decimal } from "decimal.js";
import { BusinessRuleError } from "../../core/errors.ts";

export function calculateDailyInterest(balance: Decimal.Value, dueDate: string, paymentDate: string, dailyRate: Decimal.Value = "0.0033"): Decimal {
  const days = Math.max(Math.floor((Date.parse(`${paymentDate}T00:00:00Z`) - Date.parse(`${dueDate}T00:00:00Z`)) / 86_400_000), 0);
  return new Decimal(balance).times(dailyRate).times(days).toDecimalPlaces(2, Decimal.ROUND_HALF_UP);
}
export function calculatePayment(balance: Decimal.Value, dueDate: string, paymentDate: string, paid: Decimal.Value) {
  const principal = new Decimal(balance); const interest = calculateDailyInterest(principal, dueDate, paymentDate);
  const total = principal.plus(interest); const payment = new Decimal(paid);
  if (payment.greaterThan(total)) throw new BusinessRuleError("O valor pago é maior que o saldo atualizado.");
  return { principal, interest, remaining: total.minus(payment) };
}
