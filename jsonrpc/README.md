# JSON RPC

This is a quick(-ish) JSON RPC implementation.
The libraries I looked at did not seem to support receiving notifications sent from a "server".

## Known limitations

* Batch is not supported
* Id = null is probably not handled properly, but it SHOULD not be Null in normal scenarios
* Robustness is lacking. E.g. 
  * No timeouts on calling methods
  * Input validation could be better
* Performance unknown
* Limited test coverage

## Design

The JsonRpc class takes care of _only_ the JSON RPC protocol part, connectivity is handled by transports.

In theory JsonRpc should be able to work with any transport that is passed into it.

Transports should probably be features to limit requirements
