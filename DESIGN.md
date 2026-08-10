# DESIGN.md — Automata

Fonte de verdade do sistema visual. Todas as decisões de estilo partem daqui.

## Tema

Único tema: dark. O design é definido e testado apenas neste modo.  
Implementação: tokens em `:root` e `.dark` idênticos; a classe `.dark` é
adicionada por padrão pelo ThemeProvider para ativar as variantes `dark:`
nos componentes existentes durante a migração.

## Tokens de cor

Definidos como CSS custom properties em `src/app/globals.css`.  
O bloco `@theme inline` existente propaga-os para o Tailwind automaticamente.

| Variável CSS           | Hex         | OKLCH aproximado        | Uso                                      |
|------------------------|-------------|-------------------------|------------------------------------------|
| `--background`         | `#0B0B0B`   | `oklch(0.08 0 0)`       | Fundo da aplicação                       |
| `--card`               | `#141414`   | `oklch(0.12 0 0)`       | Superfície de painel / card              |
| `--muted`              | `#1A1A1A`   | `oklch(0.15 0 0)`       | Fundo de elementos silenciados           |
| `--input`              | `#1E1E1E`   | `oklch(0.17 0 0)`       | Fundo de campos de entrada               |
| `--border`             | `#262626`   | `oklch(0.21 0 0)`       | Bordas 1px universais                    |
| `--foreground`         | `#F0F0F0`   | `oklch(0.95 0 0)`       | Texto primário                           |
| `--muted-foreground`   | `#8A8A8A`   | `oklch(0.59 0 0)`       | Texto secundário / label                 |
| `--accent`             | `#25E0C8`   | `oklch(0.82 0.13 185)`  | Nav ativo, ícone de entidade             |
| `--destructive`        | `#E05252`   | `oklch(0.60 0.20 25)`   | Erro / ação destrutiva                   |
| `--primary`            | `#F0F0F0`   | `oklch(0.95 0 0)`       | Igual a foreground                       |
| `--primary-foreground` | `#0B0B0B`   | `oklch(0.08 0 0)`       | Texto sobre fundo primário               |
| `--ring`               | `#25E0C8`   | igual a `--accent`      | Foco (outline)                           |
| `--sidebar`            | `#0F0F0F`   | `oklch(0.10 0 0)`       | Fundo da sidebar (ligeiramente diferente)|
| `--sidebar-border`     | `#262626`   | igual a `--border`      | Borda direita da sidebar                 |
| `--sidebar-primary`    | `#25E0C8`   | igual a `--accent`      | Item ativo na sidebar                    |
| `--text-label`         | `#C49A6C`   | `oklch(0.68 0.07 55)`   | Labels de pares label/valor em cards     |
| `--radius`             | `4px`       | —                       | Border-radius universal                  |

> **Accent** `#25E0C8` é a cor da marca Automata, extraída do favicon oficial.
> Nunca usar como fundo de botão — apenas texto, ícone e borda.

### Verificação de contraste (WCAG AA — mínimo 4.5:1 para texto normal)

| Par                                        | Ratio calculado | Resultado |
|--------------------------------------------|-----------------|-----------|
| `--muted-foreground` (#8A8A8A) / `--card` (#141414)       | ~5.3:1 | ✓ AA |
| `--muted-foreground` (#8A8A8A) / `--background` (#0B0B0B) | ~5.7:1 | ✓ AA |
| `--foreground` (#F0F0F0) / `--card` (#141414)             | ~18:1  | ✓ AAA |
| `--text-label` (#C49A6C) / `--card` (#141414)             | ~7.2:1 | ✓ AA  |

O `#8A8A8A` proposto passa AA em ambas as superfícies — nenhum ajuste necessário.
O `#C49A6C` proposto para labels passa AA sobre o card — nenhum ajuste necessário.

## Geometria

- `border-radius`: **4px** em tudo. Sem pílulas, sem círculos (exceto avatar).
- `box-shadow`: **zero**. Separação entre superfícies via borda 1px.
- Sem gradiente, sem glassmorphism, sem backdrop-blur.

## Tipografia

Dois níveis apenas:

| Nível          | Tamanho | Classe Tailwind   | Uso                          |
|----------------|---------|-------------------|------------------------------|
| Corpo / label  | 13px    | `text-[13px]`     | Conteúdo, labels, metadados  |
| Título de card | 14–15px | `text-sm`         | Cabeçalhos de painel         |

Hierarquia criada por cor (`--foreground` vs `--muted-foreground`), nunca por tamanho.  
Fonte: herda do layout (Geist Sans); sem troca de família.

## Botões

Elemento mais característico da linguagem "developer tool":

- Fundo **transparente**
- Borda **1px** com `--border`
- Texto **uppercase**, `letter-spacing: 0.05em`, `font-size: 11–12px`, peso medium
- Padding vertical: **6px** (`py-1.5`)
- Hover: muda apenas cor de borda e texto — **nunca o fundo**
- Sem box-shadow, sem border-radius > 4px
- Variante destrutiva: borda e texto em `--destructive`

## Cards / Painéis

- Borda 1px `--border`, sem sombra, radius 4px
- **Header**: ícone 16px + título + ação opcional alinhada à direita
- **Corpo**: pares label/valor — label em `--text-label` (13px, medium), valor em
  `--muted-foreground` (13px). Gap entre pares: 16px.
- **Footer** (quando aplicável): separado por `border-top: 1px solid --border`,
  contendo ações.

### Hierarquia de texto nos cards

Três níveis, diferenciados apenas por cor:

| Nível            | Token           | Uso                              |
|------------------|-----------------|----------------------------------|
| Título / primário| `--foreground`  | Nome do agente, valores de destaque |
| Label            | `--text-label`  | Labels de pares label/valor      |
| Secundário       | `--muted-foreground` | Valores de pares, metadados |

## Navegação lateral

- Largura: **200px** fixo, sem colapso animado
- Item: ícone 16px + label 13px, altura 32px (`h-8`)
- Grupos separados por `border-bottom: 1px solid --border`, sem título de seção
- Item ativo: texto e ícone em `--accent`, sem fundo destacado
- Padding horizontal: 12px (`px-3`)

## Inputs

- Fundo: `--input` (`#1E1E1E`)
- Borda: 1px `--border`; focus: borda em `--accent`
- Sem box-shadow
- Radius: 4px
- Texto: `--foreground`, placeholder: `--muted-foreground`

## Densidade

Espaçamento base: **4px**. Esta UI é densa de propósito.  
Gap entre itens de lista: 4px. Padding interno de card: 12px.  
Se uma tela parecer "espaçosa", há espaço demais.

## Proibido

- `box-shadow` em qualquer elemento
- `border-radius` > 4px
- Gradiente (`bg-gradient-*`)
- `backdrop-blur`
- Múltiplos tamanhos de fonte além dos dois definidos
- Accent como fundo de botão ou surface
- Título de seção na nav (usar borda de separação)
