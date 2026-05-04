# Integração Unity (Android)

## Endpoints
- `GET /health`
- `POST /matchmaking/join`
- `GET /config/client`

## Fluxo no cliente
1. Login jogador e obtenção de `player_id`.
2. Chamar `/config/client` ao abrir lobby.
3. Chamar `/matchmaking/join` ao clicar em "Jogar".
4. Exibir fila e iniciar sessão quando ticket for resolvido.

## Script C# (exemplo mínimo)
```csharp
using UnityEngine;
using UnityEngine.Networking;
using System.Collections;

public class MatchmakingClient : MonoBehaviour {
    public IEnumerator Join(string playerId) {
        var json = "{\"player_id\":\"" + playerId + "\",\"mode\":\"br\"}";
        var req = new UnityWebRequest("http://localhost:8000/matchmaking/join", "POST");
        byte[] body = System.Text.Encoding.UTF8.GetBytes(json);
        req.uploadHandler = new UploadHandlerRaw(body);
        req.downloadHandler = new DownloadHandlerBuffer();
        req.SetRequestHeader("Content-Type", "application/json");
        yield return req.SendWebRequest();
        Debug.Log(req.downloadHandler.text);
    }
}
```
