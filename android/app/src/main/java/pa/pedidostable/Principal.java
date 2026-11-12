package pa.pedidostable;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.*;
import android.widget.*;
import java.io.ByteArrayInputStream;

public class Principal extends Activity {
    private static final String DEMO = "file:///android_asset/demo.html";
    private WebView navegador;
    private String destino;

    @Override public void onCreate(Bundle estado) {
        super.onCreate(estado);
        String guardado = getPreferences(MODE_PRIVATE).getString("caja", "");
        if (valido(guardado)) abrir(guardado); else configurar();
    }

    private boolean valido(String enlace) {
        Uri uri = Uri.parse(enlace);
        if (!"http".equals(uri.getScheme()) || uri.getUserInfo() != null ||
                uri.getPort() != 8765 || !"/".equals(uri.getPath()) || uri.getQuery() != null ||
                uri.getFragment() == null || !uri.getFragment().matches("[A-Za-z0-9_-]{16,128}")) return false;
        String host = uri.getHost();
        if (host == null || !android.util.Patterns.IP_ADDRESS.matcher(host).matches()) return false;
        return host.startsWith("10.") || host.startsWith("192.168.") ||
                host.matches("172[.](1[6-9]|2[0-9]|3[01])[.][0-9]+[.][0-9]+");
    }

    private LinearLayout pantalla() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(Color.rgb(16, 30, 25));
        setContentView(layout);
        if (navegador != null) {
            navegador.stopLoading();
            navegador.destroy();
            navegador = null;
        }
        return layout;
    }

    private void configurar() {
        LinearLayout layout = pantalla();
        int margen = (int)(20 * getResources().getDisplayMetrics().density);
        layout.setPadding(margen, margen, margen, margen);
        TextView titulo = new TextView(this);
        titulo.setText("Vincular con la caja");
        titulo.setTextSize(28);
        titulo.setTextColor(Color.rgb(246, 243, 232));
        titulo.setPadding(0, margen, 0, margen);
        layout.addView(titulo);
        EditText enlace = new EditText(this);
        enlace.setSingleLine();
        enlace.setTextColor(Color.WHITE);
        enlace.setHintTextColor(Color.rgb(183, 203, 192));
        enlace.setMinHeight(Math.round(54 * getResources().getDisplayMetrics().density));
        enlace.setHint("Pega el enlace de PedidosTable de la PC");
        enlace.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        layout.addView(enlace);
        Button conectar = new Button(this);
        conectar.setText("Guardar y conectar");
        conectar.setAllCaps(false);
        conectar.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(242, 205, 132)));
        conectar.setTextColor(Color.rgb(22, 36, 27));
        conectar.setMinHeight(enlace.getMinHeight());
        layout.addView(conectar);
        conectar.setOnClickListener(v -> {
            String url = enlace.getText().toString().trim();
            if (!valido(url)) {
                enlace.setError("Copia el enlace completo que muestra la caja, incluida la clave.");
                return;
            }
            getPreferences(MODE_PRIVATE).edit().putString("caja", url).apply();
            abrir(url);
        });
        Button demo = new Button(this);
        demo.setText("Probar la demo");
        demo.setAllCaps(false);
        demo.setMinHeight(enlace.getMinHeight());
        layout.addView(demo);
        demo.setOnClickListener(v -> abrir(DEMO));
    }

    private boolean permitido(Uri uri) {
        if (DEMO.equals(destino)) return DEMO.equals(uri.toString());
        Uri caja = Uri.parse(destino);
        return caja.getScheme().equals(uri.getScheme()) && caja.getAuthority().equals(uri.getAuthority());
    }

    private void abrir(String url) {
        LinearLayout layout = pantalla();
        destino = url;
        navegador = new WebView(this);
        layout.addView(navegador, new LinearLayout.LayoutParams(-1, 0, 1));
        WebSettings opciones = navegador.getSettings();
        opciones.setUserAgentString(opciones.getUserAgentString() + " PedidosTableAndroid");
        opciones.setJavaScriptEnabled(true);
        opciones.setDomStorageEnabled(true);
        opciones.setAllowFileAccess(false);
        opciones.setAllowContentAccess(false);
        navegador.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView vista, WebResourceRequest req) {
                if ("pedidostable://conexion".equals(req.getUrl().toString()) && req.isForMainFrame() && req.hasGesture()) {
                    new AlertDialog.Builder(Principal.this)
                        .setMessage("¿Cambiar la conexión con la caja?")
                        .setNegativeButton("Cancelar", null)
                        .setPositiveButton("Continuar", (dialogo, opcion) -> configurar()).show();
                    return true;
                }
                return !permitido(req.getUrl());
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView vista, WebResourceRequest req) {
                if (permitido(req.getUrl()) || "blob".equals(req.getUrl().getScheme())) return null;
                return new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
            }
            @Override public void onReceivedError(WebView vista, WebResourceRequest req, WebResourceError error) {
                if (!req.isForMainFrame() || vista != navegador || isFinishing()) return;
                new AlertDialog.Builder(Principal.this)
                    .setMessage("Comprueba que la caja esté abierta y que ambos equipos estén en la misma red.")
                    .setPositiveButton("Reintentar", (d,i) -> vista.loadUrl(url))
                    .setNegativeButton("Cambiar conexión", (d,i) -> configurar()).show();
            }
        });
        navegador.loadUrl(url);
    }
}
