# GradPath

A React transcript-first planning prototype. Upload a local file into the left panel; GradPath acknowledges it in the chat, summarizes credit progress, then asks for planning goals.

The browser UI uses synthetic academic data for the credit summary — it does not parse or transmit the selected file. It is not academic advice or a production transcript parser.

## Run locally

```powershell
pnpm install
pnpm dev
```

Then open the local URL printed by Vite (normally `http://localhost:5173`).

The equivalent commands also work if you prefer another package manager:

```powershell
npm install
npm run dev
```

```powershell
yarn
yarn dev
```

## Build

```powershell
pnpm build
```
