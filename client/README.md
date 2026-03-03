# v3xctrl Client

React-based web client for managing v3xctrl RC car devices on your local network.

## Prerequisites

- Node.js 24+ (use `nvm install 24`)
- yarn (`npm install -g yarn`)

## Setup

```bash
cd client
yarn
```

## Development

```bash
yarn dev
```

Opens at http://localhost:5173. The app will prompt you to connect to a v3xctrl device on your local network (via subnet scan or manual IP entry).

## Testing

```bash
yarn test          # Run tests once
yarn test:watch    # Watch mode
```

## Build

```bash
yarn build
yarn preview       # Preview the production build
```

## Stack

- [Vite](https://vite.dev) - Build tool
- [React](https://react.dev) - UI framework
- [Zustand](https://zustand.docs.pmnd.rs/) - State management
- [Tailwind CSS v4](https://tailwindcss.com) - Styling
- [RJSF](https://rjsf-team.github.io/react-jsonschema-form/) - JSON Schema form editor
- [react-i18next](https://react.i18next.com/) - Internationalization
- [Vitest](https://vitest.dev) + [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/) - Testing

## Connecting to a Device

The client connects to a v3xctrl device's HTTP API running on port 80. On first load, you'll see the device discovery screen with three options:

1. **Subnet scan** - Enter a subnet base (e.g., `192.168.1`) and scan for devices
2. **Manual entry** - Type the device IP directly (e.g., `192.168.1.100` or `v3xctrl.local`)
3. **Last connected** - Reconnect to the previously used device

The device must have CORS enabled (via `flask-cors` in the web-server).
