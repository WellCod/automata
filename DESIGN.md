# DESIGN.md — Automata

Fonte de verdade do sistema visual. Todas as decisões de estilo partem daqui.

## Tema

Claro e escuro, escolhidos pelo usuário no botão do rodapé da sidebar, que alterna entre claro, escuro e sistema. Sem escolha salva, segue o sistema operacional.

Implementação:
- Tokens do claro em `:root` e do escuro em `.dark`, em `src/app/globals.css`.
- A escolha fica em `localStorage` (`automata-theme`). Um script no `<head>` (`src/lib/theme-script.ts`) aplica a classe `.dark` antes da hidratação, para a tela não abrir no tema errado.
- `src/components/layout/theme.tsx` tem o hook `useTheme` e o `ThemeToggle`. O Toaster segue o tema resolvido.

## Paleta: grafite e azul

Cinzas neutros (zinc) para superfícies, texto e bordas. Azul só em ação principal, foco, link e item ativo. Nada de cor decorativa.

| Token | Claro | Escuro | Uso |
|---|---|---|---|
| `--background` | `#FFFFFF` | `#09090B` | Fundo da aplicação |
| `--card` | `#FFFFFF` | `#18181B` | Card, painel, tabela |
| `--sidebar` | `#FAFAFA` | `#0C0C0E` | Sidebar |
| `--muted` | `#F4F4F5` | `#27272A` | Hover, fundos silenciados |
| `--border` | `#E4E4E7` | `#27272A` | Bordas 1px |
| `--input` | `#FFFFFF` | `#18181B` | Fundo de campo |
| `--foreground` | `#09090B` | `#FAFAFA` | Texto primário |
| `--muted-foreground` | `#71717A` | `#A1A1AA` | Texto secundário |
| `--text-label` | `#52525B` | `#A1A1AA` | Rótulo de par rótulo/valor |
| `--accent` | `#2563EB` | `#3B82F6` | Ação principal, foco, link, item ativo |
| `--destructive` | `#DC2626` | `#EF4444` | Erro, ação destrutiva |
| `--ring` | igual ao accent | igual ao accent | Anel de foco |

Contraste (WCAG AA, 4.5:1 para texto): `--muted-foreground` passa nos dois modos (`#71717A` sobre branco 4.8:1; `#A1A1AA` sobre `#09090B` 7.9:1). O texto branco sobre o accent passa nos dois.

Estados com cor própria usam o par claro/escuro do Tailwind: pendente `text-amber-700` / `dark:text-amber-400`, sucesso `text-green-600` / `dark:text-green-500`. Nunca `amber-400` no claro (contraste baixo).

## Geometria

- `--radius`: **6px**. Selos de estado são pílula (`rounded-full`).
- Sombra só no anel de foco; separação entre superfícies por borda 1px.
- Sem gradiente, glassmorphism ou blur.

## Tipografia

Geist Sans (variável `--font-geist-sans`), sem troca de família. Texto sempre em caixa normal, só a primeira letra maiúscula. Nada de caixa alta em botão, aba ou rótulo.

| Nível | Tamanho | Uso |
|---|---|---|
| Corpo, botão, aba | 13px | Conteúdo, campos, ações |
| Título de página e de card | 14px (`text-sm`) | Cabeçalhos |
| Apoio | 11–12px | Metadados, dicas, selos |

Hierarquia por cor (`foreground`, `muted-foreground`, `text-label`) e peso (`font-medium`), não por tamanho.

## Botões

`Button` em `src/components/ui/button.tsx` (shadcn sobre Base UI). Uma ação principal por tela.

| Variante | Aparência | Quando |
|---|---|---|
| `strong` | Azul preenchido, texto branco | Ação principal (salvar, criar, confirmar) |
| `accent` | Azul claro com texto azul | Criar novo, publicar |
| `default` | Contorno neutro | Ação secundária |
| `muted` | Contorno neutro, texto secundário | Cancelar, editar, opção de seletor |
| `destructive` | Vermelho preenchido | Confirmar exclusão |
| `subtleDestructive` | Neutro que fica vermelho no hover | Excluir antes da confirmação |
| `ghost` | Sem borda | Ícone, ação discreta |

Tamanhos: `default` (h-8), `sm` (h-7), `xs` (h-6), `icon`. Seletor de opção (período, filtro) usa `accent` no item ativo e `muted` nos demais.

## Selos de estado

`Badge` em `src/components/ui/status-badge.tsx`: pílula de 11px com fundo leve. Tons: `active` (azul), `pending` (âmbar), `neutral` (cinza), `danger` (vermelho). Texto com primeira letra maiúscula ("Rascunho pendente", "v3 ativa").

## Cards e painéis

- Borda 1px `--border`, radius 6px, fundo `--card`.
- Cabeçalho: título 14px e ação opcional à direita.
- Corpo: pares rótulo/valor, rótulo em `--text-label`, valor em `--muted-foreground`.

## Abas

`Tabs` em `src/components/ui/tabs.tsx`: texto 13px; a aba ativa fica com texto primário e linha inferior azul, sem fundo.

## Navegação lateral

- Largura fixa de 200px, fundo `--sidebar`.
- Item: ícone 16px e rótulo 13px, altura 32px; ativo em azul, sem fundo.
- Rodapé: e-mail de quem está logado, seletor de tema e sair. Itens só de owner (Usuários) não aparecem para os outros papéis.

## Inputs

Fundo `--input`, borda 1px `--border` e foco com borda azul. Placeholder em `--muted-foreground`.

## Densidade

Base de 4px. O painel é denso de propósito: gap de 4px em listas e padding de 12px em card.

## Gráficos

Recharts via `ChartContainer` do shadcn (`src/components/ui/chart.tsx`), em `src/components/metrics-charts.tsx`.

- Séries: `--chart-1` (azul `#2563EB` / `#3B82F6`) e `--chart-2` (laranja `#EA580C`); erro em `--chart-error` (`#DC2626` / `#EF4444`). Validadas no validador de paleta contra o `--card` de cada modo (lightness na faixa, CVD ΔE ≥ 30, contraste ≥ 3:1).
- Bloqueio por guardrail: `--chart-blocked` (`#B45309` / `#C98500`), empilhado abaixo do sucesso em "Conversas por dia": ao lado do erro, âmbar e vermelho se confundem para daltonismo deutan. A ordem bloqueado → sucesso → erro passa no validador nos dois temas.
- Um eixo por gráfico; medidas de escala diferente vão em gráficos separados.
- Linha de 2px sem marcadores, barra com topo arredondado de 4px, grade só horizontal.
- Legenda sempre que houver duas séries, tooltip no hover e tabela com os mesmos dados em "Ver tabela".

## Proibido

- Caixa alta em texto de interface
- Cor saturada fora de ação, foco e estado
- Mais de uma ação principal (`strong`) por tela
- Gradiente, glow ou blur
- `amber-400`, `red-400` e similares claros como texto no tema claro
