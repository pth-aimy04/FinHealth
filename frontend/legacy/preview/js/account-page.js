/** Email action entry point; account links never expose tokens in request URLs. */
import { bindAccount } from "./accounts.js";
bindAccount().catch(() => {
  document.getElementById("account-page").append(document.createTextNode("Không kết nối được hệ thống tài khoản."));
});
