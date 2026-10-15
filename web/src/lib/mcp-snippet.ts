// Configuração de cliente MCP (Claude Desktop, Cursor) apontando para o /mcp da instância
export function mcpSnippet(mcpUrl: string | null | undefined, token: string): string {
  return JSON.stringify(
    {
      mcpServers: {
        automata: {
          url: mcpUrl ?? "https://SUA-API/mcp",
          headers: { Authorization: `Bearer ${token}` },
        },
      },
    },
    null,
    2,
  );
}
