import assert from "node:assert/strict";
import test from "node:test";
import { BusinessRuleError } from "../src/core/errors.ts";
import { decreaseBatchBalance, validateExpiryWindow } from "../src/modules/catalog/service.ts";
import { calculateDailyInterest, calculatePayment } from "../src/modules/customers/credit-service.ts";
import { calculateCashDifference, calculateSaleTotal, requireOpenCash } from "../src/modules/sales/service.ts";

test("calcula total da venda e quebra de caixa com precisão decimal", () => {
  assert.equal(calculateSaleTotal([{ quantity: 2, unitPrice: 10, discount: 1 }]).toFixed(2), "19.00");
  const cash = calculateCashDifference("100.00", "250.00", "345.00");
  assert.equal(cash.expected.toFixed(2), "350.00"); assert.equal(cash.difference.toFixed(2), "-5.00");
});
test("preserva regras de caixa e estoque", () => {
  assert.throws(() => requireOpenCash({ status: "fechado" }), BusinessRuleError);
  assert.equal(decreaseBatchBalance({ quantity: "10" }, "3").toString(), "7");
  assert.throws(() => validateExpiryWindow(366), BusinessRuleError);
});
test("calcula juros e baixa de crediário", () => {
  assert.equal(calculateDailyInterest("100", "2026-07-01", "2026-07-11").toFixed(2), "3.30");
  assert.equal(calculateDailyInterest("100", "2026-07-10", "2026-07-01").toFixed(2), "0.00");
  assert.throws(() => calculatePayment("100", "2026-07-01", "2026-07-02", "200"), BusinessRuleError);
});
