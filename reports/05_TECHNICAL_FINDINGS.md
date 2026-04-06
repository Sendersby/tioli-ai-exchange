# Technical Findings — TiOLi AGENTIS
## Comprehensive Audit | 2026-04-06

### API Endpoints
| Finding | Status |
|---------|--------|
| All public endpoints return structured JSON | PASS |
| Dashboard endpoints reject unauthenticated with 302 redirect | PASS |
| /api/v1/health returns operational status | PASS |
| All Boardroom GET endpoints respond with valid JSON | PASS |
| Rate limiting active (slowapi 100/min + nginx 10r/s) | PASS |
| Paywall middleware integrated | PASS |

### Error Handling
| Test | Before Audit | After Audit |
|------|-------------|-------------|
| Non-existent URL | 500 (cascade) | 404 (branded error page) |
| Non-existent API endpoint | JSON 404 | JSON 404 |
| Malformed input | Returns 422 | PASS |

### Security
| Header | agentisexchange.com | exchange.tioli.co.za |
|--------|-------------------|---------------------|
| HSTS | YES (31536000s) | YES |
| X-Content-Type-Options | nosniff | nosniff |
| X-Frame-Options | SAMEORIGIN | DENY |
| X-XSS-Protection | 1; mode=block | 1; mode=block |
| Content-Security-Policy | Added (nginx) | YES (FastAPI) |
| Permissions-Policy | Added (nginx) | YES (FastAPI) |
| server_tokens off | Enabled | N/A (Cloudflare) |
| Cookie secure + samesite | Fixed | Fixed |
| SSL certificate | Valid until Jun 2026 | Valid until Jun 2026 |
| SSL auto-renewal | Certbot timer active | Certbot timer active |
| Rate limiting | nginx + slowapi | nginx + slowapi |
| Localhost exempted from rate limit | YES (geo block) | YES |

### SEO
| Element | Status |
|---------|--------|
| sitemap.xml | 19 URLs with lastmod and priority |
| robots.txt | Correct directives, /api/ and /dashboard/ blocked |
| JSON-LD structured data | Present on landing page |
| Meta titles | Standardized across all 20 pages |
| Meta descriptions | Present on most pages (oversight missing) |
| OG tags | Present on main pages (some operator pages missing) |
| Canonical URLs | Correct for both domains |

### Performance
| Page | Target | Actual |
|------|--------|--------|
| Landing page | <2s | ~0.1s (localhost) |
| Dashboard | <2s | <0.1s + redirect |
| Boardroom | <2s | ~0.07s |
| API health | <500ms | <0.01s |

### JWT/Auth
| Setting | Value | Status |
|---------|-------|--------|
| SECRET_KEY length | 87 characters | PASS (>64 required) |
| Token format | Base64-encoded, high entropy | PASS |

### Fixes Applied This Session
1. 404 handler: fixed cascading 500 error
2. 5 missing FastAPI routes: added static file fallbacks
3. Cookie security: added secure=True, samesite=lax
4. CSP + Permissions-Policy: added to public domain nginx
5. server_tokens off: enabled
6. Localhost rate limit exemption: geo block added
7. Sitemap: expanded from 9 to 19 URLs with lastmod/priority
8. Title tags: standardized across all pages
