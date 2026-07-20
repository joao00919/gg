# Gerenciar Tickets — referência completa 4.3.18

Esta revisão reorganiza o módulo **Gerenciar Ticket** com base no fluxo observável do vídeo enviado.

## Interface implementada

- Tela `Painel > Gerenciar Tickets` com contador de painéis.
- Botões `Ligar/Desligar Todos`, `Criar Painel`, `Editar Painel` e `Voltar`.
- Criação de painel por modal, com validação de nome repetido.
- Criação e gerenciamento de até 25 opções por painel.
- Edição e remoção múltipla de opções.
- Painel de status com modo Canal/Tópico, horário, ZYNEX AI e estado do painel.
- Botões `Editar Opções`, `Editar Mensagens`, `Modo`, `Horário de Atendimento`, `ZYNEX AI` e `Preferências`.
- Configuração de categoria, canal e cargos por opção.
- Publicação, atualização e exclusão do painel.
- Exclusão controlada dos tickets vinculados ao painel.

## Mensagens

- Mensagem do painel.
- Mensagem de abertura por opção.
- Mensagem de fechamento.
- Notificação de usuário e equipe.
- Adicionar e remover usuário.
- Assumir e transferir ticket.
- Criar/solicitar call.
- Transcript.
- Modos Embed, Texto Simples e Container V2.
- Editor de botão, conteúdo e visualização prévia.

## Preferências

- Sistema de transcripts.
- Setup do membro.
- Setup do atendente.
- Fechamento automático e regras de encerramento.
- Formulários por opção.

## Robustez

- Toda alteração relevante marca o painel como pendente de publicação.
- Emojis personalizados possuem fallback Unicode.
- Ações e selects desconhecidos retornam erro visível em vez de expirar silenciosamente.
- Painéis e opções recebem estruturas padrão completas no momento da criação.
