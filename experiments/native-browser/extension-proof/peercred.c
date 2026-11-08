#define _GNU_SOURCE
#include <sys/socket.h>
#include <unistd.h>
#include <stdint.h>
#include <stddef.h>
typedef struct napi_env__* napi_env;typedef struct napi_value__* napi_value;typedef struct napi_callback_info__* napi_callback_info;typedef napi_value(*napi_callback)(napi_env,napi_callback_info);
extern int napi_get_cb_info(napi_env,napi_callback_info,size_t*,napi_value*,napi_value*,void**);extern int napi_get_value_int32(napi_env,napi_value,int32_t*);extern int napi_create_int32(napi_env,int32_t,napi_value*);extern int napi_create_function(napi_env,const char*,size_t,napi_callback,void*,napi_value*);extern int napi_set_named_property(napi_env,napi_value,const char*,napi_value);extern int napi_throw_error(napi_env,const char*,const char*);
static napi_value uid(napi_env e,napi_callback_info info){size_t n=1;napi_value arg,result;int32_t fd;struct ucred c;socklen_t len=sizeof(c);if(napi_get_cb_info(e,info,&n,&arg,0,0)||n!=1||napi_get_value_int32(e,arg,&fd)||getsockopt(fd,SOL_SOCKET,SO_PEERCRED,&c,&len)||len!=sizeof(c)){napi_throw_error(e,0,"SO_PEERCRED failed");return 0;}napi_create_int32(e,(int32_t)c.uid,&result);return result;}
__attribute__((visibility("default")))napi_value napi_register_module_v1(napi_env e,napi_value exports){napi_value fn;napi_create_function(e,"peerUid",7,uid,0,&fn);napi_set_named_property(e,exports,"peerUid",fn);return exports;}
typedef struct {int version;unsigned int flags;const char*filename;napi_value(*register_func)(napi_env,napi_value);const char*name;void*priv;void*reserved[4];} napi_module;
extern void napi_module_register(napi_module*);
static napi_module module={1,0,__FILE__,napi_register_module_v1,"mgu_peercred",0,{0}};
__attribute__((constructor))static void register_legacy(void){napi_module_register(&module);}
