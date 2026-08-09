# Perennia React App - Quick Start Guide

## Prerequisites
- Node.js 16+ installed
- npm or yarn package manager

## Installation

### 1. Install Dependencies
```bash
npm install
```

### 2. Run Development Server
```bash
npm run dev
```

The app will start at `http://localhost:5173` (Vite default port)

### 3. Build for Production
```bash
npm run build
```

Output files will be in the `dist` directory.

### 4. Preview Production Build
```bash
npm run preview
```

---

## Project Structure

```
perennia-updated/
├── src/
│   ├── components/
│   │   ├── chat/           # Chat interface components
│   │   ├── hero/           # Homepage hero section
│   │   ├── layout/         # Layout components (TopBar)
│   │   ├── booking/        # Appointment booking components
│   │   └── ui/             # Reusable UI components
│   ├── context/            # React Context (Language)
│   ├── api/                # API client
│   ├── styles/             # Global styles & tokens
│   ├── data/               # Static data & content
│   ├── hooks/              # Custom React hooks
│   └── App.jsx             # Main app component
├── public/                 # Static assets
├── index.html              # HTML entry point
├── vite.config.js          # Vite configuration
└── package.json            # Dependencies
```

---

## Key Features

### ✅ Pass 1 Completed
- **Professional & Colorful Design**: Enhanced color palette with vibrant golds, blues, and accent colors
- **Fixed Header Menu**: Horizontal fixed header (64px desktop / 56px mobile)
- **2026 Copyright Footer**: Added to both home and chat pages
- **Chat Input Visibility**: Proper spacing and scrollable layout

### 🔄 Features in Progress
- **Pass 2**: Admin section with configurable settings
- **Pass 3**: Appointment booking and leads management

---

## Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server with hot reload |
| `npm run build` | Build optimized production bundle |
| `npm run preview` | Preview production build locally |
| `npm run lint` | Run ESLint code quality checks |

---

## Configuration

### Color Customization
Edit `src/styles/tokens.css` to change colors:

```css
:root {
  --gold: #fbbf24;           /* Primary accent */
  --navy-1: #0a0e27;         /* Darkest shade */
  --blue-light: #3b82f6;     /* Secondary color */
  /* ... more colors ... */
}
```

### Layout Adjustments
Modify `src/styles/tokens.css` for spacing:

```css
:root {
  --header-h: 64px;          /* Header height */
  --space-3: 12px;           /* Base spacing unit */
  --content-max: 1180px;     /* Max content width */
}
```

---

## Browser Support

| Browser | Version | Status |
|---------|---------|--------|
| Chrome | 90+ | ✅ Supported |
| Firefox | 88+ | ✅ Supported |
| Safari | 14+ | ✅ Supported |
| Edge | 90+ | ✅ Supported |
| Mobile Chrome | 90+ | ✅ Supported |
| Mobile Safari | 14+ | ✅ Supported |

---

## Performance Tips

1. **Development**: Hot module replacement (HMR) enabled for fast refreshes
2. **Production**: Minified CSS/JS and image optimization
3. **Animations**: GPU-accelerated with `transform` and `filter`
4. **Mobile**: Respects `prefers-reduced-motion` for accessibility

---

## Troubleshooting

### Port Already in Use
If port 5173 is occupied:
```bash
npm run dev -- --port 3000
```

### Modules Not Found
Clear node_modules and reinstall:
```bash
rm -rf node_modules package-lock.json
npm install
```

### Build Fails
Check Node.js version:
```bash
node --version  # Should be 16 or higher
```

---

## API Configuration

The app connects to PHP backend APIs. Configure the API endpoint in:
- `src/api/client.js` - Update base URL if needed

### Available Endpoints
- `/api/chat.php` - Chat functionality
- `/api/appointments.php` - Appointment booking
- `/api/faq.php` - FAQ data

---

## Language Support

The app supports multiple languages via Context API:
- English (default)
- Arabic (RTL support)

Switch languages using the toggle button in the header.

---

## Mobile Responsiveness

Tested breakpoints:
- **Mobile**: 320px - 480px (full-width, compact header)
- **Tablet**: 481px - 767px (adjusted spacing)
- **Desktop**: 768px+ (full layout with centered nav)

---

## Getting Help

### Common Issues

**Issue**: Styles not applying
- Clear browser cache (Ctrl+Shift+Delete)
- Hard refresh (Ctrl+Shift+R)

**Issue**: API calls failing
- Check backend server is running
- Verify CORS configuration
- Check browser console for errors

**Issue**: Animations stuttering
- Check GPU acceleration in browser devtools
- Reduce motion for performance testing

---

## Development Workflow

1. **Feature Branch**: Create branch for new features
2. **Local Testing**: Test thoroughly on desktop and mobile
3. **Build Check**: Run `npm run build` to verify
4. **Code Quality**: Run `npm run lint` before commit
5. **Production**: Deploy `dist/` folder contents

---

## Deployment

### Static Hosting (Netlify, Vercel, GitHub Pages)
```bash
npm run build
# Upload `dist/` folder
```

### Apache/Nginx
```bash
npm run build
# Copy `dist/` contents to web root
```

### Docker
Create a `Dockerfile`:
```dockerfile
FROM node:18 as build
WORKDIR /app
COPY . .
RUN npm install && npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

---

## Version Information

- **React**: 19.2.8
- **Vite**: 8.2.0
- **Node**: 16+ required
- **Last Updated**: August 8, 2026

---

## Next Steps

1. ✅ **Pass 1 Complete**: Professional design and UI improvements
2. 🚀 **Pass 2 Ready**: Admin section and configuration system
3. 📅 **Pass 3 Planned**: Appointment and leads functionality

---

For detailed improvements, see `PASS1_IMPROVEMENTS.md`
