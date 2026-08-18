# 배포 파이프라인

`main` 브랜치에 push(=PR merge)되면 GitHub Actions가 test → Docker Hub push → EC2 배포까지 자동으로 한다.
(`.github/workflows/ci.yml`의 `deploy` job, `build-and-push`가 성공해야 실행됨)

## 자동으로 되는 것 (여기까지 구현 완료)

1. `pytest` 통과 확인
2. `{DOCKERHUB_USERNAME}/ai-fighters:main` 이미지 build & push
3. EC2에 SSH 접속 → `docker compose -f docker-compose.prod.yml pull && up -d` → 재기동
4. `/health` 헬스체크

## DB는 별도 RDS 없이 EC2 안에 번들로 띄운다

`docker-compose.prod.yml`에 `api`와 함께 `db`(Postgres 컨테이너, `pgdata` 볼륨으로 영속화)를 같이 정의해뒀다.
그래서 EC2에서 결정할 게 "RDS냐 컨테이너냐"가 아니라 그냥 `docker compose up`ㅡ뿐이다 — 별도 DB 프로비저닝/네트워크 설정 불필요.

## EC2 쪽에서 준비해야 하는 것 (아직 안 됨 — 재원 확인 필요)

1. **인스턴스 생성 및 8000 포트 보안그룹 오픈** (또는 앞단에 리버스 프록시 붙일 거면 해당 포트만)
2. `EC2_DEPLOY_PATH` 경로에 이 레포의 [docker-compose.prod.yml](../docker-compose.prod.yml)을 그대로 복사해두기
3. 같은 경로에 `.env` 파일 생성 — `DATABASE_URL`, `GEMINI_API_KEY`, `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` 등 [.env.example](../.env.example) 기준으로 실제 값 채워서 (`DATABASE_URL`의 host는 `db`로). 이 파일은 서버에만 두고 git에는 절대 올리지 않는다.
4. GitHub Actions 배포용 SSH 키 페어 생성 → **공개키는 EC2 `~/.ssh/authorized_keys`에, 개인키는 아래 GitHub Secrets에**

## GitHub Secrets (Settings → Secrets and variables → Actions, 재원이 등록)

| 이름 | 값 |
|---|---|
| `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` | 이미 등록되어 있음 (build-and-push에서 기존에 쓰던 것) |
| `EC2_HOST` | EC2 퍼블릭 IP 또는 도메인 |
| `EC2_USER` | SSH 접속 계정 (예: `ubuntu`) |
| `EC2_SSH_KEY` | 위에서 만든 배포용 SSH 개인키 전체 내용 |
| `EC2_DEPLOY_PATH` | EC2에서 `docker-compose.prod.yml`이 있는 경로 (예: `/home/ubuntu/ai-fighters`) |

전부 등록되기 전까지는 `deploy` job이 `main` push 시 자동으로 돌지만 SSH 접속 단계에서 실패한다 — 실패해도 test/build-and-push 결과에는 영향 없음.
