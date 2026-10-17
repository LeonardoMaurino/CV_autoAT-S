// Código do nó "Config" do workflow principal (cópia pra facilitar a leitura;
// o que roda no n8n é o que está dentro do JSON em workflows/).
// ================= CONFIG =================
// Cole aqui as URLs de busca do LinkedIn, com os filtros que quiser (cargo, cidade, remoto...).
// O filtro de tempo (f_TPR) e a ordenação (sortBy) são ajustados automaticamente lá embaixo,
// então pode colar o link do jeito que ele aparece no navegador.
const buscas = [
  // 2 buscas com OR. Só funciona sem aspas e sem parênteses: assim o LinkedIn soma os termos
  // (com aspas/parênteses ele mistura tudo e um dos termos some). Ele ordena por relevância,
  // então a busca de RPA vem primeiro pra não ficar sem vaga quando a de dev lotar as 10.
  'https://www.linkedin.com/jobs/search/?keywords=RPA%20OR%20cientista&geoId=105871508',
  'https://www.linkedin.com/jobs/search/?keywords=desenvolvedor%20OR%20IA&geoId=105871508',
  // infra: sem essa busca quase não chega vaga de infra pra marcar quem acompanha infra. Descomente pra ativar:
  // 'https://www.linkedin.com/jobs/search/?keywords=infraestrutura&geoId=105871508',
  // busca booleana que estava na V2 (retirado pois o linkedin mudou o formato de sua pesquisa)

  // 'https://www.linkedin.com/jobs/search/?f_PP=104746682&f_TPR=r1800&geoId=105871508&keywords=(%22Analista%20de%20Dados%22%20OR%20%22Data%20Analyst%22%20OR%20%22Data%20Scientist%22%20OR%20RPA%20OR%20Python%20OR%20%22Machine%20Learning%22%20OR%20Desenvolvedor)&sortBy=R',
];

// Máximo de vagas processadas por rodada, somando todas as buscas.
// Se tiver mais que isso, as buscas do topo da lista têm prioridade.
const maxVagas = 10;

// Quantas vagas o Apify traz por busca (cada vaga trazida é cobrada: US$ 0,002 no plano grátis).
// A rodada das 6h00 pega um pouco mais porque cobre a madrugada inteira.
const vagasPorBusca = 5;
const vagasPorBuscaMadrugada = 10;

// Habilidades que o ATS costuma procurar. As que aparecem na vaga vão pro prompt do currículo
// e pra mensagem do Telegram (mesma lista do relatório semanal).
const habilidades = {
  'Python': ['python'], 'SQL': ['sql'], 'Excel': ['excel'], 'Power BI': ['power bi', 'powerbi'],
  'UiPath': ['uipath'], 'Power Automate': ['power automate'], 'Automation Anywhere': ['automation anywhere'],
  'Blue Prism': ['blue prism'], 'Java': ['java'], 'C#/.NET': ['c#', '.net', 'dotnet'],
  'JavaScript/TypeScript': ['javascript', 'typescript', 'node.js', 'nodejs'], 'React': ['react'],
  'AWS': ['aws'], 'Azure': ['azure'], 'Google Cloud': ['gcp', 'google cloud'], 'Docker': ['docker'],
  'Kubernetes': ['kubernetes', 'k8s'], 'Git': ['git', 'github', 'gitlab'], 'APIs REST': ['api', 'apis', 'restful'],
  'Machine Learning': ['machine learning', 'scikit-learn', 'sklearn'],
  'IA generativa/LLM': ['llm', 'llms', 'genai', 'ia generativa', 'generative ai', 'openai', 'langchain'],
  'Pandas': ['pandas'], 'Spark': ['spark', 'pyspark'], 'Scrum/Ágil': ['scrum', 'ágil', 'agile', 'kanban'],
  'Inglês': ['inglês', 'english'], 'Espanhol': ['espanhol', 'spanish'],
};

// Áreas: palavras-chave procuradas no TÍTULO da vaga.
// Maiúsculas e acentos não importam, e a palavra tem que aparecer inteira ("dev" não bate com "devops").
// exceto: palavras que tiram a vaga da área.
const palavrasRPA = ['rpa', 'automação de processos', 'hiperautomação', 'hyperautomation', 'uipath',
  'automation anywhere', 'blue prism', 'power automate', 'process automation'];
const palavrasDev = ['desenvolvedor', 'desenvolvedora', 'developer', 'dev', 'programador', 'programadora',
  'desenvolvimento de sistemas', 'desenvolvimento de software', 'analista de sistemas',
  'engenheiro de software', 'engenheira de software', 'software engineer',
  'backend', 'back-end', 'frontend', 'front-end', 'fullstack', 'full stack'];
const palavrasIA = ['ia', 'ai', 'inteligência artificial', 'artificial intelligence', 'machine learning', 'ml',
  'deep learning', 'llm', 'llms', 'genai', 'ia generativa', 'generative ai', 'mlops', 'nlp',
  'visão computacional', 'computer vision'];
const palavrasDados = ['cientista de dados', 'cientista dados', 'data scientist', 'ciência de dados', 'data science'];

const areas = {
  'RPA': { palavras: palavrasRPA },
  // "Analista de Automação" costuma ser RPA; as exceções tiram automação industrial, de testes e de marketing
  'Automação': {
    palavras: ['automação', 'automation'],
    exceto: ['industrial', 'elétrica', 'mecatrônica', 'clp', 'plc', 'scada', 'predial', 'residencial',
      'teste', 'testes', 'test', 'testing', 'qa', 'marketing'],
  },
  'Infra': {
    palavras: ['infraestrutura', 'infra', 'infrastructure', 'sysadmin', 'administrador de sistemas',
      'system administrator', 'devops', 'sre', 'site reliability', 'cloud', 'linux', 'windows server',
      'datacenter', 'data center', 'noc', 'analista de redes', 'técnico de redes', 'engenheiro de redes',
      'administrador de redes', 'network engineer', 'network administrator', 'suporte técnico',
      'suporte de ti', 'help desk', 'helpdesk', 'service desk'],
    exceto: ['redes sociais', 'social media'],
  },
  // dev, IA e ciência de dados juntos; vaga com RPA no título fica só com o pessoal de RPA
  'Dev / IA / Dados': {
    palavras: [...palavrasDev, ...palavrasIA, ...palavrasDados],
    exceto: palavrasRPA,
  },
};

// Quem marcar no Telegram, e em quais áreas.
// telegram: o @username da pessoa ou o ID numérico (ela descobre o dela mandando uma mensagem pro @userinfobot).
//           Vazio = aparece só o nome, sem notificar. A pessoa precisa estar no grupo pra ser notificada.
const interessados = [
  { nome: 'Pessoa de RPA', telegram: '', areas: ['RPA', 'Automação'] },
  { nome: 'Pessoa de infra', telegram: '', areas: ['Infra'] },
  { nome: 'Pessoa de dev', telegram: '', areas: ['Dev / IA / Dados'] },
];
// ==========================================

// O workflow roda a cada 30 min, das 6h00 às 22h30, e pega só vagas dos últimos 30 min (menos concorrência).
// A rodada das 6h00 cobre a madrugada (22h30 -> 6h00); as outras cobrem 30 min + 5 min de folga.
// As vagas repetidas por causa da folga são descartadas no nó "Vagas novas".
const primeiraDoDia = $now.hour === 6 && $now.minute < 30;
const janelaSegundos = primeiraDoDia ? 7.5 * 3600 + 300 : 30 * 60 + 300;
const limitePorBusca = primeiraDoDia ? vagasPorBuscaMadrugada : vagasPorBusca;

const urls = buscas.map((u) => {
  const [base, query = ''] = u.split('?');
  const params = query.split('&').filter((p) => p && !/^(f_TPR|sortBy)=/.test(p));
  params.push(`f_TPR=r${janelaSegundos}`, 'sortBy=DD');
  return `${base}?${params.join('&')}`;
});

// Monta a marcação de cada pessoa já no formato HTML que o Telegram entende
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const pessoas = interessados.map(({ nome, telegram = '', areas: suasAreas = [] }) => {
  const errada = suasAreas.find((a) => !areas[a]);
  if (errada) throw new Error(`Config: a área "${errada}" de ${nome} não existe. As áreas são: ${Object.keys(areas).join(', ')}`);
  const t = telegram.trim();
  let mencao;
  if (!t) mencao = `<b>${esc(nome)}</b>`;
  else if (/^@[A-Za-z][A-Za-z0-9_]{3,31}$/.test(t)) mencao = t;
  else if (/^\d+$/.test(t)) mencao = `<a href="tg://user?id=${t}">${esc(nome)}</a>`;
  else throw new Error(`Config: o telegram de ${nome} precisa ser um @username ou um ID numérico (veio "${telegram}")`);
  return { nome, mencao, areas: suasAreas };
});

return [{ json: { urls, maxVagas, limitePorBusca, areas, interessados: pessoas, habilidades } }];
