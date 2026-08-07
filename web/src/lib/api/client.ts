import createClient from "openapi-fetch";
import type { paths } from "./schema.d.ts";

// O client chama o BFF Next.js — nunca a API Python diretamente.
// Sem credenciais aqui: a chave privada fica no Route Handler.
const client = createClient<paths>({ baseUrl: "/api" });

export default client;
