# Actuators!
We are abandoning the notiion of sMAP instances as web servers -- they are now almost entirely pub-sub clients. Using
sMAP instances as web servers meant that they needed to be globally addressable, which is hard to do while accounting
for NAT traversal. The pub-sub model gets us around this, but it does mean that we now need to replicate the kind of
"push" semantics we are used to thinking about for actuation.

Actuation will be handled as subscriptions. Some of these will be specialized, such as a specific subscription to
a specific scheduler or a specific controller. But there should also be an avenue for general-purpose/override 
actuation, should the driver decide to allow it (maybe this is a configuration option so the authors don't have 
to worry about it?)

How do we protect against the case where someone else adds metadata that's the same? Is this a trusted domain?

Right now, there is no transaction manager or other arbiter for multiple actuation requests against a device. In that
absence, it makes sense to push that responsibility into the driver.
