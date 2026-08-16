# Frontend Design

Use ao construir interfaces web (landing, cardápio, painel admin).

## Princípios

- Hierarquia visual clara: um CTA principal por tela
- Tipografia legível (Inter, system-ui) e contraste WCAG AA
- Mobile-first: layout responsivo com breakpoints 640 / 768 / 1024
- Espaçamento consistente (múltiplos de 4px ou 8px)
- Estados hover/focus/disabled em botões e links

## Stack padrão PKF

- HTML semântico + CSS moderno (flex/grid, variáveis CSS)
- JS vanilla ou módulos leves; evite bundlers pesados em MVP
- Ícones SVG inline ou emoji com parcimônia

## Checklist antes de entregar

- [ ] Funciona em viewport 375px e 1280px
- [ ] Formulários com labels e feedback de erro
- [ ] Cores da marca aplicadas via CSS variables
- [ ] `index.html` na raiz do projeto para preview PKF
