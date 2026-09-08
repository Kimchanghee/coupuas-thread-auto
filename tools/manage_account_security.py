"""Interactive MFA setup. Run with python tools/manage_account_security.py."""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import auth_client


def main():
    username = input("아이디: ").strip()
    password = getpass.getpass("비밀번호: ")
    result = auth_client.login(username, password)
    if result.get("status") == "MFA_REQUIRED":
        result = auth_client.login(
            username, password, mfa_code=getpass.getpass("인증 앱/복구 코드: ").strip()
        )
    if result.get("status") is not True:
        print(auth_client.friendly_login_message(result))
        return 1
    token = auth_client.get_auth_state().get("token")

    def call(path, payload):
        response = auth_client._session.post(
            f"{auth_client.API_SERVER_URL}/user/mfa/{path}",
            json=payload,
            headers=auth_client._build_auth_headers(token),
            timeout=12,
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise RuntimeError(
                "보안 설정을 완료하지 못했습니다. 입력값과 서버 설정을 확인해주세요."
            )
        return response.json()

    try:
        action = input("설정(enroll) 또는 해제(disable): ").strip()
        proof = auth_client._normalize_password_for_backend(password)
        if action == "disable":
            call(
                "disable",
                {
                    "password": proof,
                    "code": getpass.getpass("인증 앱/복구 코드: ").strip(),
                },
            )
            print(
                "2단계 인증을 해제했습니다. 다른 세션과 자동 로그인은 취소되었습니다."
            )
        elif action == "enroll":
            data = call("enroll", {"password": proof})
            print(
                "인증 앱에 ThreadPilot 계정을 추가하고 아래 설정 키를 직접 입력하세요."
            )
            print(data["secret"])
            data = call(
                "confirm", {"code": getpass.getpass("인증 앱 6자리 코드: ").strip()}
            )
            print(
                "2단계 인증 설정 완료. 아래 일회용 복구 코드를 안전한 별도 장소에 보관하세요."
            )
            for code in data["recovery_codes"]:
                print(code)
        else:
            print("작업을 취소했습니다.")
    finally:
        password = None
        auth_client.logout()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
