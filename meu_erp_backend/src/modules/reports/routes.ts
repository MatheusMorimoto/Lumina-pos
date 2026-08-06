import type { FastifyPluginAsync, FastifyRequest } from "fastify";
import { BusinessRuleError } from "../../core/errors.ts";
import { requestDatabase, requestRepository } from "../../shared/http.ts";

type Sale = Record<string, unknown> & { sale_payments?: Array<Record<string, unknown>> };
function nextDay(value: string): string { const date = new Date(`${value}T00:00:00Z`); date.setUTCDate(date.getUTCDate() + 1); return date.toISOString().slice(0, 10); }
async function reportSales(request: FastifyRequest, start: string, end: string): Promise<Sale[]> {
  const db = requestDatabase(request); const repo = requestRepository(request);
  return repo.rows(db.from("sales").select("*,sale_payments(*)").eq("status", "completed").gte("sold_at", start).lt("sold_at", nextDay(end))) as Promise<Sale[]>;
}
const sum = (values: unknown[]): number => values.reduce<number>((total, value) => total + Number(value ?? 0), 0);

function simplePdf(lines: string[]): Buffer {
  const text = lines.join("\\n").replaceAll("(", "\\(").replaceAll(")", "\\)");
  const stream = Buffer.from(`BT /F1 10 Tf 40 800 Td (${text}) Tj ET`, "latin1");
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
    `<< /Length ${stream.length} >>\nstream\n${stream.toString("latin1")}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let body = "%PDF-1.4\n"; const offsets: number[] = [];
  objects.forEach((object, index) => { offsets.push(Buffer.byteLength(body, "latin1")); body += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = Buffer.byteLength(body, "latin1"); body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  body += offsets.map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("");
  body += `trailer << /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(body, "latin1");
}

export const registerReportRoutes: FastifyPluginAsync = async (app) => {
  app.get<{ Querystring: { date?: string } }>("/reports/dashboard", async (request) => {
    const date = request.query.date ?? new Date().toISOString().slice(0, 10); const rows = await reportSales(request, date, date);
    const total = sum(rows.map((row) => row.total)); const methods = new Set(rows.flatMap((row) => row.sale_payments ?? []).map((p) => String(p.method)));
    return { date, sales_count: rows.length, gross_sales: total, average_ticket: rows.length ? total / rows.length : 0,
      payments: Object.fromEntries([...methods].map((method) => [method, sum(rows.flatMap((row) => row.sale_payments ?? []).filter((p) => p.method === method).map((p) => p.amount))])) };
  });
  app.get<{ Querystring: { start: string; end: string; group_by?: string } }>("/reports/closures", async (request) => {
    const groupBy = request.query.group_by ?? "day";
    if (!["day", "week", "month", "year"].includes(groupBy)) throw new BusinessRuleError("Agrupamento inválido.");
    const rows = await reportSales(request, request.query.start, request.query.end); const groups = new Map<string, number>();
    for (const row of rows) {
      const date = new Date(String(row.sold_at)); let key = date.toISOString().slice(0, 10);
      if (groupBy === "month") key = key.slice(0, 7); if (groupBy === "year") key = key.slice(0, 4);
      if (groupBy === "week") { const first = new Date(Date.UTC(date.getUTCFullYear(), 0, 1)); key = `${date.getUTCFullYear()}-W${String(Math.ceil((((date.getTime() - first.getTime()) / 86400000) + first.getUTCDay() + 1) / 7)).padStart(2, "0")}`; }
      groups.set(key, (groups.get(key) ?? 0) + Number(row.total));
    }
    return [...groups].sort(([a], [b]) => a.localeCompare(b)).map(([period, total]) => ({ period, total }));
  });
  app.get<{ Querystring: { start: string; end: string } }>("/reports/dre", async (request) => {
    const rows = await reportSales(request, request.query.start, request.query.end); const revenue = sum(rows.map((r) => r.total));
    const fees = sum(rows.flatMap((r) => r.sale_payments ?? []).filter((p) => p.status === "fee").map((p) => p.amount));
    return { start: request.query.start, end: request.query.end, gross_revenue: revenue,
      discounts: sum(rows.map((r) => r.discount)), fees, net_result: revenue - fees };
  });
  app.get<{ Querystring: { start: string; end: string; format?: string } }>("/reports/closures/export", async (request, reply) => {
    const format = request.query.format ?? "csv"; const rows = await reportSales(request, request.query.start, request.query.end);
    if (format === "pdf") return reply.type("application/pdf").header("Content-Disposition", "attachment; filename=closures.pdf")
      .send(simplePdf([`Fechamentos ${request.query.start} a ${request.query.end}`, ...rows.map((row) => `${row.sold_at}  R$ ${row.total}`)]));
    if (format !== "csv") throw new BusinessRuleError("Formato inválido. Use PDF ou CSV.");
    const escape = (value: unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const csv = ["id,sold_at,total,status", ...rows.map((row) => [row.id, row.sold_at, row.total, row.status].map(escape).join(","))].join("\r\n");
    return reply.header("Content-Type", "text/csv; charset=utf-8").header("Content-Disposition", "attachment; filename=closures.csv").send(csv);
  });
};
