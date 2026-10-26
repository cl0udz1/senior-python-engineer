class RetryableConflict(Exception): pass
def run_transaction(connect, work, max_attempts=3):
    if max_attempts<1:raise ValueError('max_attempts must be positive')
    for attempt in range(max_attempts):
        connection=connect()
        try:
            result=work(connection);connection.commit();return result
        except RetryableConflict:
            connection.rollback()
            if attempt+1==max_attempts:raise
        except BaseException:
            connection.rollback();raise
        finally:connection.close()
