from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile.frontend"


def test_frontend_dockerfile_preserves_standalone_runtime_contract() -> None:
    dockerfile = DOCKERFILE.read_text()

    assert "FROM base AS deps" in dockerfile
    assert "COPY --from=deps /app/node_modules ./node_modules" in dockerfile
    assert "output: \"standalone\"" in (ROOT / "frontend/next.config.ts").read_text()
    assert "RUN mkdir -p public && npm run build" in dockerfile
    assert "COPY --from=builder /app/public ./public" in dockerfile
    assert "COPY --from=builder /app/.next/standalone ./" in dockerfile
    assert "COPY --from=builder /app/.next/static ./.next/static" in dockerfile
    assert "ENV NODE_ENV=production" in dockerfile
    assert "ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}" in dockerfile
    assert 'CMD ["node", "server.js"]' in dockerfile
    assert 'CMD ["npm", "start"]' not in dockerfile
