use strict; use warnings; use IO::Socket::INET; use IO::Socket::UNIX; use IO::Select;
$SIG{CHLD}='IGNORE';
my $server=IO::Socket::INET->new(LocalAddr=>'127.0.0.1',LocalPort=>$ENV{MGU_NATIVE_HTTP_PORT},Listen=>16,ReuseAddr=>1) or die "private loopback listener: $!";
while(my $client=$server->accept()) {
 my $pid=fork(); die "fork: $!" unless defined $pid; if($pid){close($client);next;}
 close($server);my $upstream=IO::Socket::UNIX->new(Peer=>$ENV{MGU_NATIVE_HTTP_SOCKET},Type=>SOCK_STREAM) or die "private unix upstream: $!";
 my $sel=IO::Select->new($client,$upstream);
 while(my @ready=$sel->can_read(15)) {
  my $done=0;
  for my $from(@ready){my $n=sysread($from,my $buf,16384);if(!defined($n)||!$n){$done=1;last;}my $to=fileno($from)==fileno($client)?$upstream:$client;my $off=0;while($off<$n){my $w=syswrite($to,$buf,$n-$off,$off);if(!defined($w)||!$w){$done=1;last;}$off+=$w;}last if $done;}
  last if $done;
 }
 close($client);close($upstream);exit 0;
}
