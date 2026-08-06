import assert from "node:assert/strict";
import test from "node:test";
import { publicRegistration, registrationSchema, validCnpj, validCpf } from "../src/modules/registration/schema.ts";

const common = {
  email: " USER@Example.COM ", password: "senha-segura1", password_confirmation: "senha-segura1",
  phone: "(65) 99999-9999", postal_code: "78000-000", street: "Rua Principal", address_number: "25",
  neighborhood: "Centro", city: "Cuiabá", state: "mt",
};

test("normaliza e valida cadastro individual", () => {
  const data = registrationSchema.parse({ ...common, person_type: "individual", cpf: "529.982.247-25", full_name: "Pessoa Exemplo", birth_date: "1990-05-10", tax_regime: "pessoa_fisica" });
  assert.equal(data.email, "user@example.com"); assert.equal(data.cpf, "52998224725"); assert.equal(data.state, "MT"); assert.equal(validCpf(data.cpf), true);
  assert.equal("password" in publicRegistration(data), false);
});

test("aceita contrato aninhado de cadastro", () => {
  const data = registrationSchema.parse({ person_type: "individual", name: "Pessoa Exemplo", cpf: "529.982.247-25", birth_date: "1990-05-10",
    email: "pessoa@example.com", phone: "65999999999", password: "SenhaSegura1", password_confirmation: "SenhaSegura1",
    address: { postal_code: "78000000", street: "Rua Principal", number: "25", district: "Centro", city: "Cuiabá", state: "MT" } });
  assert.equal(data.full_name, "Pessoa Exemplo"); assert.equal(data.address_number, "25");
});

test("valida documentos brasileiros", () => {
  assert.equal(validCpf("111.111.111-11"), false); assert.equal(validCnpj("11.222.333/0001-81"), true);
});
