// Código do nó "Monta prompt" do workflow principal (cópia pra facilitar a leitura;
// o que roda no n8n é o que está dentro do JSON em workflows/).
// Roda uma vez para cada vaga. Edite o texto do prompt e o título do doc à vontade.
const config = $('Config').first().json;

// alguns textos vêm com código HTML ("QA&#32", "P&amp;D")
const decodifica = (s) => String(s ?? '')
  .replace(/&#x([0-9a-f]+);?/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
  .replace(/&#(\d+);?/g, (_, d) => String.fromCodePoint(Number(d)))
  .replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/&amp;/g, '&')
  .trim();
const vaga = { ...$json, title: decodifica($json.title), companyName: decodifica($json.companyName) };

// Compara textos ignorando maiúsculas e acentos, e só vale palavra inteira ("dev" não bate com "devops")
const normaliza = (s) =>
  ` ${String(s ?? '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/[^a-z0-9#+]+/g, ' ').trim()} `;
const contem = (texto, termos = []) => termos.some((t) => normaliza(t).trim() && texto.includes(normaliza(t)));
const titulo = normaliza(vaga.title);
const textoVaga = normaliza(`${vaga.title} ${vaga.descriptionText ?? ''}`);

// Palavras-chave que o ATS desta vaga deve procurar (lista no nó Config)
const palavrasChave = Object.entries(config.habilidades ?? {})
  .filter(([, termos]) => contem(textoVaga, termos))
  .map(([nome]) => nome);

const prompt = `Gere o currículo e a carta para esta vaga:

Cargo: ${vaga.title}
Empresa: ${vaga.companyName}
${palavrasChave.length ? `Palavras-chave que o ATS desta vaga deve procurar: ${palavrasChave.join(', ')}
(use esses termos exatamente assim no currículo e na carta, mas só os que eu realmente tenho)
` : ''}Descrição: ${vaga.descriptionText}`;

const titulo_cv = `CV - Seu Nome - ${vaga.companyName}`;

// Concorrência: o LinkedIn mostra "seja um dos 25 primeiros" (vem como 25) e para de contar em 200
const bruto = String(vaga.applicantsCount ?? '').replace(/\D/g, '');
const nCandidatos = bruto === '' ? null : Number(bruto);
const candidatos = nCandidatos === null ? null
  : nCandidatos <= 25 ? 'até 25 candidatos 🟢'
  : `${nCandidatos}${nCandidatos >= 200 ? '+' : ''} candidatos ${nCandidatos < 100 ? '🟡' : '🔴'}`;

// Mensagem do Telegram em HTML: só &, < e > precisam de escape
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const local = [vaga.location, vaga.companyAddress?.streetAddress].filter(Boolean).join(', ');
const linkVaga = String(vaga.link ?? '').split('?')[0];

const msg = [
  `🎯 <b>${esc(vaga.title)}</b>`,
  `🏢 ${esc(vaga.companyName)}`,
  candidatos && `👥 ${candidatos}`,
  local && `📍 ${esc(local)}`,
  palavrasChave.length && `🧩 ${esc(palavrasChave.join(' · '))}`,
  linkVaga && `📶 <a href="${esc(linkVaga)}">Ver vaga no LinkedIn</a>`,
].filter(Boolean).join('\n\n');

// Quem marcar: descobre as áreas da vaga pelo título (palavras-chave do nó Config)
// e marca quem acompanha alguma delas.
const areasDaVaga = Object.keys(config.areas)
  .filter((a) => contem(titulo, config.areas[a].palavras) && !contem(titulo, config.areas[a].exceto));
const mencoes = [...new Set(config.interessados
  .filter((p) => p.areas.some((a) => areasDaVaga.includes(a)))
  .map((p) => p.mencao))];

return {
  json: {
    ...vaga,
    // o Apify manda o salário em "salary" (quase nunca preenchido no Brasil)
    salario: String(vaga.salary ?? '').trim() || (vaga.salaryInfo ?? []).filter(Boolean).join(' – '),
    palavras_chave: palavrasChave.join(', '),
    prompt,
    titulo_cv,
    msg,
    areas_da_vaga: areasDaVaga.join(', '),
    // vai no fim da mensagem do Telegram; vazio quando a vaga não é de nenhuma área
    marcar: mencoes.length ? `\n\n🔔 ${mencoes.join(' ')}` : '',
  },
};
