# Como colocar o site no ar sem aparecer como dono

Este guia é para quem quer publicar o radar e **não quer o próprio nome ligado ao projeto**. São duas partes: o que já está protegido e o passo a passo para o site ficar acessível.

## O que já está protegido neste repositório

- Nenhum arquivo cita o nome de usuário do GitHub: o `cidade.json` está com `"repositorio": ""`, então o site não mostra link para o código.
- A licença está em nome de "Radar Cidades".
- Os commits são assinados como `Radar Cidades <radar-cidades@users.noreply.github.com>`, e os automáticos como `radar-bot`.
- O robô se identifica para a Câmara só como `RadarCidades/2.0 (monitoramento cidadao de dados publicos)`.

## O que ainda liga o projeto a você

1. **O dono do repositório.** Enquanto o repositório estiver em uma conta pessoal, quem tiver acesso a ele vê a conta. Privado, só você vê.
2. **O endereço do GitHub Pages.** O endereço gratuito é `SEU_USUARIO.github.io/...`: mostra o usuário. Por isso este guia usa outro serviço para o site.
3. **Um domínio próprio.** No registro.br, o titular de um `.com.br` é público (consulta WHOIS). Se quiser domínio, use um subdomínio gratuito do serviço de hospedagem ou um domínio registrado com proteção de privacidade.
4. **O acesso à Câmara.** As coletas saem dos servidores do GitHub, não do seu computador. Rodar a coleta no seu computador expõe o seu IP nos registros do sistema da Câmara; prefira deixar o GitHub Actions fazer.

## Caminho recomendado: repositório privado + Cloudflare Pages

O repositório fica privado (ninguém vê o código nem o dono) e o site fica público em `nome-que-voce-escolher.pages.dev`. Tudo gratuito.

### 1. Crie uma conta separada na Cloudflare

Use um e-mail que não tenha o seu nome (crie um só para isso). Em https://dash.cloudflare.com/sign-up.

### 2. Crie o projeto do site

No painel da Cloudflare: **Workers & Pages → Create → Pages → Upload assets** (envio direto). Dê o nome do projeto, por exemplo `radar-rioclaro`. O endereço será `radar-rioclaro.pages.dev`. Pode enviar um arquivo qualquer só para criar o projeto; o GitHub vai substituir.

### 3. Crie a chave de acesso

**My Profile → API Tokens → Create Token → Custom token**, com a permissão **Account → Cloudflare Pages → Edit**. Copie o token. Anote também o **Account ID**, que aparece na página inicial de Workers & Pages.

### 4. Guarde a chave no GitHub

No repositório: **Settings → Secrets and variables → Actions**.

Na aba **Secrets**, crie:

| Nome | Valor |
|---|---|
| `CLOUDFLARE_API_TOKEN` | o token do passo 3 |
| `CLOUDFLARE_ACCOUNT_ID` | o Account ID |

Na aba **Variables**, crie:

| Nome | Valor |
|---|---|
| `CLOUDFLARE_PROJECT` | o nome do projeto (ex.: `radar-rioclaro`) |
| `SITE_URL` | o endereço do site (ex.: `https://radar-rioclaro.pages.dev`) |

### 5. Publique

**Actions → Atualizar dados e publicar → Run workflow.** Em alguns minutos o site está no ar no endereço `.pages.dev`. Daí em diante atualiza sozinho todo dia às 06:17.

Sem os segredos da Cloudflare, o fluxo roda, atualiza os dados e simplesmente não publica.

## Se quiser anonimato completo

O caminho acima esconde você do público. Para que nem o GitHub tenha o projeto na sua conta pessoal:

1. Crie um e-mail novo e, com ele, uma conta nova no GitHub (nome neutro, como `radar-rioclaro`).
2. Nessa conta, crie um repositório vazio.
3. No seu computador, na pasta do projeto:
   ```bash
   git remote set-url origin https://github.com/CONTA_NOVA/NOME_DO_REPOSITORIO.git
   git push -u origin main
   ```
   O Git vai pedir o login: entre com a conta nova.
4. Apague o repositório da conta pessoal (**Settings → Danger Zone → Delete this repository**).

Com a conta nova o repositório pode até ser público e usar o GitHub Pages normal (**Settings → Pages → Source: GitHub Actions**), porque o endereço `CONTA_NOVA.github.io` não diz quem você é.

## Cuidados no dia a dia

- Não faça commits a partir do seu computador sem conferir `git config user.name` e `git config user.email` nesta pasta: devem ser os do projeto, não os seus.
- Não divulgue o site a partir de perfis pessoais se a ideia é não ser associado a ele.
- O conteúdo do site é todo de fonte oficial e pública, com link para o documento original. Mantenha assim: não acrescente opinião nem texto que não venha dos dados.
