// a API responde {"detail": "..."}; o texto vira a mensagem do modo teste
export async function failureText(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // corpo vazio ou fora de JSON
  }
  return `Erro ao executar (HTTP ${response.status}).`;
}
