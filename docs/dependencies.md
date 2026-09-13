# Dependências e licenças

Decisão de 2026-09-07. Única dependência direta de runtime: pdfplumber, necessária
para caracteres, linhas, fontes e posições; isolada atrás de adapter. Builder,
CLI, XML, ZIP, publicação, supervisão e fixtures usam stdlib. Sem dependência de
OCR/IA/GUI/rede. Versões fixadas em constraints.txt; resolução com hashes será
registrada em requirements.lock (8 pacotes) e requirements-dev.lock (22 pacotes).
Dependências não são copiadas para o wheel do Prometeu.

## Resolução examinada

Fonte oficial: metadados das releases em https://pypi.org/pypi/{nome}/{versão}/json;
URLs dos projetos, data de manutenção, requisitos transitivos e campo vulnerabilities
preservados em dependency-survey.json. Licenças desconhecidas nos metadados de
mypy-extensions e pyproject-hooks foram confirmadas no LICENSE do wheel oficial.

| Pacote | Versão | Licença declarada/verificada |
| --- | --- | --- |
| pdfplumber | 0.11.10 | MIT |
| pytest | 9.1.1 | MIT |
| ruff | 0.16.6 | MIT |
| mypy | 2.3.1 | MIT |
| build | 1.6.0 | MIT |
| setuptools | 84.0.0 | MIT |
| uv | 0.12.10 | MIT OR Apache-2.0 |
| pdfminer.six | 20260107 | MIT |
| pillow | 12.3.0 | MIT-CMU |
| pypdfium2 | 5.13.0 | BSD-3-Clause, Apache-2.0, dependency licenses |
| iniconfig | 2.3.0 | MIT |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.6.0 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| typing-extensions | 4.16.0 | PSF-2.0 |
| mypy-extensions | 1.1.0 | MIT (LICENSE do wheel) |
| pathspec | 1.1.1 | MPL-2.0 |
| librt | 0.15.0 | MIT |
| ast-serialize | 0.10.0 | MIT |
| pyproject-hooks | 1.2.0 | MIT |
| charset-normalizer | 3.5.1 | MIT |
| cryptography | 50.0.1 | Apache-2.0 OR BSD-3-Clause |
| cffi | 2.1.1 | MIT-0 |
| pycparser | 3.0 | BSD-3-Clause |

pytest, Ruff, mypy e build são dev solicitadas; setuptools é backend de build.
uv é ferramenta local de bootstrap, não dependência do pacote: wheel macOS arm64
17.238.363 bytes, SHA-256 5dc26c73826d2119292d49d71c5a9d5ba9dd97dd02459d816b8226f47f3dc6bd.
Python gerenciado é somente ambiente de desenvolvimento, não redistribuído.

Transitivas runtime: pdfminer.six, Pillow, pypdfium2, charset-normalizer,
cryptography, cffi, pycparser. Demais pacotes são dev/build. pathspec é MPL-2.0:
ferramenta de desenvolvimento separada, sem modificação/cópia no código do Prometeu;
se redistribuída, preservar licença e disponibilidade do código coberto.

## Componentes nativos e distribuição

Foram examinados wheels macOS arm64 antes da instalação. pdfplumber: 60.047 bytes,
MIT no LICENSE; pdfminer.six é Python, usa criptografia transitiva. pypdfium2 5.13.0
traz PDFium 153.0.7999.0, wheel 3.507.415 bytes, flags vazias (sem V8/XFA).
Pillow 12.3.0: wheel cp311 4.785.266 bytes; cryptography 50.0.1 abi3: 4.010.153 bytes,
Rust/OpenSSL; cffi 2.1.1 cp311: 184.168 bytes, extensão C/libffi. Ruff/uv são binários
Rust; mypy/librt/ast-serialize podem usar extensões compiladas. Não se promete
instalação puramente Python nem footprint constante entre plataformas.

[Licenciamento oficial pypdfium2](https://pypdfium2.readthedocs.io/en/stable/readme.html#licensing):
wrapper Apache-2.0/BSD-3-Clause; PDFium BSD e avisos transitivos em BUILD_LICENSES.
Foram identificados abseil (Apache-2.0), agg23 (permissiva), fast_float/simdutf/lcms
(MIT), FreeType (FTL), ICU (Unicode e avisos próprios), libjpeg-turbo (IJG/BSD/zlib),
OpenJPEG (BSD-2), libpng (PNG), libtiff (permissiva), LLVM libc (Apache-2.0 com
exceções), pdfium-binaries (MIT) e zlib. Não usamos exemplos CC-BY como código.

Análise explícita GPL: o aviso ICU inclui script de configuração GPLv3 com exceção
Autoconf, cujo próprio aviso declara condição satisfeita no ICU4C; não incorporamos
esse script no Prometeu. O LICENSE de Pillow distingue liblzma (domínio público)
de ferramentas/scripts/build GPL/LGPL não contidos no binário. FreeType oferece
escolha FTL ou GPL; usamos FTL. Estas menções não justificam rotular toda a árvore
como GPL nem apagar os avisos. As dependências incluem trabalho do FreeType Project
e da Independent JPEG Group; mantenha seus créditos/licenças em redistribuições.

Pillow inclui codecs/bibliotecas nativas (Brotli, lcms2, PNG, JPEG, FreeType,
HarfBuzz, OpenJPEG, AVIF, zlib-ng, WebP, X11, lzma, TIFF); os avisos são preservados
no LICENSE de 70.282 bytes do wheel. O core textual não chama renderização de
PDFium nem decodificação/exportação de imagens. Isso reduz alcance, não elimina
risco de importações/componentes transitivos. Antes de empacotar executável
standalone, revisar novamente licenças e linkage de cada wheel/plataforma.

## Manutenção e segurança

As versões escolhidas têm releases recentes verificadas no inventário; nenhum
advisory apareceu no campo vulnerabilities do PyPI para essas versões na consulta.
Isso não é varredura exaustiva nem garantia de ausência de risco.

Ambos os advisories oficiais do pdfminer.six indicam correção a partir de 20251230;
20260107 está fora das faixas afetadas consultadas:
[GHSA-wf5f-4jwr-ppcp](https://github.com/pdfminer/pdfminer.six/security/advisories/GHSA-wf5f-4jwr-ppcp)
e [GHSA-f83h-ghpp-7wcc](https://github.com/pdfminer/pdfminer.six/security/advisories/GHSA-f83h-ghpp-7wcc).
Não se escolheu versão antiga para reduzir transitivas. Atualizações futuras
exigem revisar árvore, advisories, testes e hashes; não atualizar no runtime.

Instalação/desenvolvimento podem usar PyPI e documentação oficial. Conversão não
instala pacotes/fontes/modelos/schemas e não usa rede. EPUBCheck será ferramenta
local opcional, não incorporada nem baixada automaticamente. A licença Apache-2.0
do código original não licencia livros, logo, fontes ou anexos do usuário.


## Desktop — 2026-09-13

Dependências separadas em apps/desktop; opcionais para usuários da CLI. Nenhuma
mudança nas dependências Python. Versões/licenças consultadas no npm antes de
instalar; confirmadas nos package.json e arquivos LICENSE locais após instalação.
package-lock.json fixa a resolução npm e integridades. Não há CDN em runtime.

| Dependência | Versão | Finalidade | Licença | Necessidade |
| --- | --- | --- | --- | --- |
| @tauri-apps/api | 2.11.1 | IPC e Channel locais | Apache-2.0 OR MIT | Desktop runtime |
| lucide-react | 1.45.0 | Ícones locais | ISC | Desktop runtime |
| react | 19.3.0 | Interface | MIT | Desktop runtime |
| react-dom | 19.3.0 | Renderização DOM | MIT | Desktop runtime |
| @tauri-apps/cli | 2.11.4 | Comandos de desenvolvimento/build nativo | Apache-2.0 OR MIT | Só desenvolvimento |
| @testing-library/react | 16.3.3 | Testes de renderização | MIT | Só desenvolvimento |
| @testing-library/user-event | 14.6.7 | Interações acessíveis nos testes | MIT | Só desenvolvimento |
| @types/node | 26.5.1 | Tipos das ferramentas Node | MIT | Só desenvolvimento |
| @types/react | 19.3.0 | Tipos React | MIT | Só desenvolvimento |
| @types/react-dom | 19.3.0 | Tipos React DOM | MIT | Só desenvolvimento |
| @vitejs/plugin-react | 6.1.1 | Transformação/refresh React | MIT | Só desenvolvimento |
| eslint | 10.10.0 | Lint | MIT | Só desenvolvimento |
| eslint-plugin-react-hooks | 7.1.1 | Regras de hooks | MIT | Só desenvolvimento |
| jsdom | 30.0.1 | DOM de testes | MIT | Só desenvolvimento |
| typescript | 6.0.3 | Tipos e compilação | Apache-2.0 | Só desenvolvimento |
| typescript-eslint | 8.70.0 | Lint TypeScript | MIT | Só desenvolvimento |
| vite | 8.3.0 | Servidor local e bundle | MIT | Só desenvolvimento |
| vitest | 5.0.0 | Executor de testes | MIT | Só desenvolvimento |

Rust: versões e licenças verificadas nos metadados oficiais do crates.io antes de
adicionar. Rust não disponível; Cargo.lock/transitivas e licenças de distribuição
nativa ainda devem ser resolvidos/revisados no próximo incremento.

| Dependência | Versão | Finalidade | Licença | Necessidade |
| --- | --- | --- | --- | --- |
| tauri | 2.11.5 | Janela e IPC | Apache-2.0 OR MIT | Desktop runtime |
| tauri-build | 2.6.3 | Configuração/ACL do shell | Apache-2.0 OR MIT | Build |
| tauri-plugin-dialog | 2.7.3 | Seletor de PDF nativo | Apache-2.0 OR MIT | Desktop runtime, somente Rust |
| serde | 1.0.229 | Contratos tipados de IPC | MIT OR Apache-2.0 | Desktop runtime |
| serde_json | 1.0.151 | Transporte JSON com Python | MIT OR Apache-2.0 | Desktop runtime |

Lucide declara ISC nesta versão; não presumir MIT. TypeScript 7.0.2 foi
descartado antes da instalação por incompatibilidade com typescript-eslint;
6.0.3 satisfaz os peers sem --force. Testing Library/React, Vite, Vitest e
ESLint têm transitivas no lock; nenhum Playwright foi adicionado. Ícones e fontes
externas não são baixados no runtime. Antes de empacotar instaladores, preservar
licenças/avisos transitivos de todas as plataformas, como já exigido para o core.
