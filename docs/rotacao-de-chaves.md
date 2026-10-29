# Troca das chaves da instância

Passo a passo da [ADR-0026](adr/0026-rotacao-de-chaves.md). São duas chaves independentes, e cada uma tem a sua troca:

- **Par JWT** (`JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`): assina e verifica sessões do painel e tokens de integração.
- **Chave dos segredos** (`MCP_SECRETS_KEY`): cifra os headers dos servidores MCP, os webhooks da suíte, os destinos de alerta e as credenciais dos conectores.

A página **Chaves** do painel (só para o owner) acompanha a troca. Ela mostra o que ainda depende da chave velha e avisa quando as variáveis `*_PREVIOUS_*` podem sair.

## Antes de começar: a chave vazou?

| Situação | Como trocar |
|---|---|
| Troca de rotina, saída de alguém do time, prazo da política | Com chave anterior: ninguém cai |
| **Chave privada JWT exposta** (repositório, log, variável no lugar errado) | **Sem** `JWT_PREVIOUS_PUBLIC_KEY`. Quem tem a privada velha assina tokens novos que a anterior aceitaria. A troca corta todas as sessões e todos os tokens de integração de uma vez; reemita os tokens depois |
| Chave dos segredos exposta | Com chave anterior, e o comando de recifrar logo em seguida. A anterior só lê o que já está gravado; ela não deixa ninguém gravar |

A ação manual da Fase 11 é o caso do meio: a chave privada foi mandada ao Vercel e o histórico público tem um par de teste. Troque o par **sem** chave anterior.

## Par JWT

### 1. Gerar o par novo

```bash
openssl genrsa 2048 > jwt-novo.pem
openssl rsa -in jwt-novo.pem -pubout > jwt-novo.pub
```

No `.env` do compose, o PEM vai entre aspas duplas, em uma linha, com `\n` literal. No Vercel e no Railway, o arquivo pode ir como está.

```bash
awk 'NF {sub(/\r/, ""); printf "%s\\n",$0}' jwt-novo.pem
```

Guarde os arquivos fora do repositório e apague-os depois de configurar.

### 2. Painel primeiro

No painel (container `web` ou Vercel):

- `JWT_PUBLIC_KEY` = pública nova;
- `JWT_PREVIOUS_PUBLIC_KEY` = pública atual, que vira a anterior. Deixe vazia se a chave vazou.

O painel vai antes porque passa a aceitar as duas chaves. Se a API trocasse primeiro, ela emitiria tokens que o painel ainda recusa, e o login entraria em loop.

```bash
vercel env rm JWT_PUBLIC_KEY production --yes
vercel env add JWT_PUBLIC_KEY production < jwt-novo.pub
vercel env add JWT_PREVIOUS_PUBLIC_KEY production < jwt-atual.pub
vercel --prod --yes
```

### 3. Depois a API

Na API:

- `JWT_PRIVATE_KEY` = privada nova;
- `JWT_PUBLIC_KEY` = pública nova;
- `JWT_PREVIOUS_PUBLIC_KEY` = pública antiga. Deixe vazia se a chave vazou.

Reinicie a API. A partir daí todo token sai com o `kid` da chave nova.

No compose: atualize o `.env` e rode `docker compose up -d api web`. Quem usa o `scripts/deploy.sh` precisa atualizar também o `.deploy-keys`, senão o próximo deploy volta a mandar o par velho.

### 4. Migrar quem depende da chave velha

- **Sessões do painel** vencem em 1 hora e voltam com a chave nova no próximo login. Não há o que fazer.
- **Tokens de integração** aparecem na página Chaves e ficam marcados com "chave anterior" em Integrações. Para cada um: emita um token novo com os mesmos agentes, entregue ao sistema que integra e revogue o antigo depois que ele trocar. Os tokens que não forem reemitidos caem quando a anterior sair, no máximo em 90 dias, que é a validade máxima.

### 5. Tirar a anterior

Quando a página Chaves mostrar zero tokens na chave anterior e zero de antes do `kid`, remova `JWT_PREVIOUS_PUBLIC_KEY` da API e do painel e reinicie os dois.

## Chave dos segredos

### 1. Gerar a chave nova

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Configurar e reiniciar

Na API:

- `MCP_SECRETS_KEY` = chave nova;
- `MCP_SECRETS_PREVIOUS_KEY` = chave atual.

Reinicie a API. Tudo o que for gravado daqui em diante já sai com a nova, e o que está gravado continua legível pela anterior.

### 3. Recifrar

```bash
docker compose exec api python -m app.rotate_secrets
```

No Railway, use `railway run python -m app.rotate_secrets`. O comando recifra as quatro tabelas numa transação só e informa quantos registros mudaram em cada uma. Pode rodar de novo sem efeito.

Se algum segredo não abrir com nenhuma das duas chaves, o comando para sem gravar nada e informa a tabela e o id. Isso acontece quando a chave original já tinha se perdido. Recadastre esse segredo no painel e rode o comando de novo.

### 4. Tirar a anterior

Quando a página Chaves mostrar zero segredos na chave anterior, remova `MCP_SECRETS_PREVIOUS_KEY` e reinicie a API. Guarde a chave nova onde ficam os outros segredos da instância. Perder essa chave obriga a recadastrar todos os segredos.

## Senha do owner

Senha não é chave e não entra nesta troca. Para uma senha que vazou, entre como owner, troque a senha em **Usuários** e confira os outros owners. A troca de senha corta na hora as sessões abertas da pessoa.
