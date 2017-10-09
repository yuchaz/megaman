import numpy as np
import scipy as sp
import scipy.sparse

def precompute_optimzation_Y(laplacian_matrix, n_samples, relaxation_kwds):
    """compute Lk, neighbors and subset to index map for projected == False"""
    relaxation_kwds.setdefault('presave',False)
    relaxation_kwds.setdefault('presave_name','pre_comp_current.npy')
    relaxation_kwds.setdefault('verbose',False)
    if relaxation_kwds['verbose']:
        print ('Making Lk and nbhds')
    Lk_tensor, nbk, si_map = \
        compute_Lk(laplacian_matrix, n_samples, relaxation_kwds['subset'])
    if relaxation_kwds['presave']:
        raise NotImplementedError('Not yet implemented presave')
    return { 'Lk': Lk_tensor, 'nbk': nbk, 'si_map': si_map }

def compute_Lk(laplacian_matrix,n_samples,subset):
    """
    Compute sparse L matrix, neighbors and subset to L matrix index map.

    Returns
    -------
    Lk_tensor : array-like. Length = n
        each component correspond to the sparse matrix of Lk, which is
        generated by extracting the kth row of laplacian and removing zeros.
    nbk : array-like. Length = n
        each component correspond to the neighbor index of point k, which is
        used in slicing the gradient, Y or S arrays.
    si_map : dictionary.
        subset index to Lk_tensor (or nbk) index mapping.
    """
    Lk_tensor = []
    nbk = []
    row,column = laplacian_matrix.T.nonzero()
    nnz_val = np.squeeze(np.asarray(laplacian_matrix.T[(row,column)]))
    sorted_col_args = np.argsort(column)
    sorted_col_vals = column[sorted_col_args]

    breaks_row = np.diff(row).nonzero()[0]
    breaks_col = np.diff(sorted_col_vals).nonzero()[0]

    si_map = {}

    for idx,k in enumerate(subset):
        if k == 0:
            nbk.append( column[:breaks_row[k]+1].T )
            lk = nnz_val[np.sort(sorted_col_args[:breaks_col[k]+1])]
        elif k == n_samples-1:
            nbk.append( column[breaks_row[k-1]+1:].T )
            lk = nnz_val[np.sort(sorted_col_args[breaks_col[k-1]+1:])]
        else:
            nbk.append( column[breaks_row[k-1]+1:breaks_row[k]+1].T )
            lk = nnz_val[np.sort(
                sorted_col_args[breaks_col[k-1]+1:breaks_col[k]+1])]

        npair = nbk[idx].shape[0]
        rk = (nbk[idx] == k).nonzero()[0]
        Lk = sp.sparse.lil_matrix((npair,npair))
        Lk.setdiag(lk)
        Lk[:,rk] = -(lk.reshape(-1,1))
        Lk[rk,:] = -(lk.reshape(1,-1))
        Lk_tensor.append(Lk)
        si_map[k] = idx

    assert len(Lk_tensor) == subset.shape[0], \
        'Size of Lk_tensor should be the same as subset.'
    return Lk_tensor, nbk, si_map

def precompute_optimzation_S(laplacian_matrix,n_samples,relaxation_kwds):
    """compute Rk, A, ATAinv, neighbors and pairs for projected mode"""
    relaxation_kwds.setdefault('presave',False)
    relaxation_kwds.setdefault('presave_name','pre_comp_current.npy')
    relaxation_kwds.setdefault('verbose',False)
    if relaxation_kwds['verbose']:
        print ('Pre-computing quantities Y to S conversions')
        print ('Making A and Pairs')
    A, pairs = makeA(laplacian_matrix)
    if relaxation_kwds['verbose']:
        print ('Making Rk and nbhds')
    Rk_tensor, nbk = compute_Rk(laplacian_matrix,A,n_samples)
    # TODO: not quite sure what is ATAinv? why we need this?
    ATAinv = np.linalg.pinv(A.T.dot(A).todense())
    if relaxation_kwds['verbose']:
        print ('Finish calculating pseudo inverse')
    if relaxation_kwds['presave']:
        raise NotImplementedError('Not yet implemented presave')
    return { 'RK': Rk_tensor, 'nbk': nbk,
             'ATAinv': ATAinv, 'pairs': pairs, 'A': A }

def makeA(laplacian_matrix):
    """
    This function create the all neighbor permutations.
    The output A multiply by Y will be [ Y_i - Y_j ].T for all j > i
    So the maximum will be C^n_2. But it will be less than this value
    because of the sparseness of L.

    Returns
    -------
    A : sparse matrix, shape (N_pairs, n_samples)
        Operator for Y projection transformation.
    pairs : matrix, shape (N_pairs, 2)
        Pairs index for A, first column is the row and second is the col.
    """
    n = laplacian_matrix.shape[0]
    row,col = sp.sparse.triu(laplacian_matrix,k=1).nonzero()
    pairs = np.asarray((row,col)).T
    N = row.shape[0]
    A = sp.sparse.csr_matrix((np.ones(N), (np.arange(N),row)), shape=(N,n)) + \
        sp.sparse.csr_matrix((-1*np.ones(N), (np.arange(N),col)), shape=(N,n))
    return A, pairs

def compute_Rk(L,A,n_samples):
    # TODO: need to inspect more into compute Rk.
    """
    Compute sparse L matrix and neighbors.

    Returns
    -------
    Rk_tensor : array-like. Length = n
        each component correspond to the sparse matrix of Lk, which is
        generated by extracting the kth row of laplacian and removing zeros.
    nbk : array-like. Length = n
        each component correspond to the neighbor index of point k, which is
        used in slicing the gradient, Y or S arrays.
    """
    laplacian_matrix = L.copy()
    laplacian_matrix.setdiag(0)
    laplacian_matrix.eliminate_zeros()

    n = n_samples
    Rk_tensor = []
    nbk = []
    row_A,column_A = A.T.nonzero()

    row,column = laplacian_matrix.nonzero()
    nnz_val = np.squeeze(np.asarray(laplacian_matrix.T[(row,column)]))
    sorted_col_args = np.argsort(column)
    sorted_col_vals = column[sorted_col_args]

    breaks_row_A = np.diff(row_A).nonzero()[0]
    breaks_col = np.diff(sorted_col_vals).nonzero()[0]

    for k in range(n_samples):
        if k == 0:
            nbk.append( column_A[:breaks_row_A[k]+1].T )
            Rk_tensor.append(
                nnz_val[np.sort(sorted_col_args[:breaks_col[k]+1])])
        elif k == n_samples-1:
            nbk.append( column_A[breaks_row_A[k-1]+1:].T )
            Rk_tensor.append(
                nnz_val[np.sort(sorted_col_args[breaks_col[k-1]+1:])])
        else:
            nbk.append( column_A[breaks_row_A[k-1]+1:breaks_row_A[k]+1].T )
            Rk_tensor.append(nnz_val[np.sort(
                sorted_col_args[breaks_col[k-1]+1:breaks_col[k]+1])])

    return Rk_tensor, nbk
